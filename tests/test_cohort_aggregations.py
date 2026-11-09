"""Synthetic, deterministic cohort aggregation checks. No patient data or DB access."""

from datetime import date

import pandas as pd
import pytest
from app.routes import cohort_route as route


@pytest.fixture(params=["yes", "no"], ids=["demo", "production"])
def execute(monkeypatch, tmp_path, request):
    monkeypatch.setattr(route.settings, "saved_searches", str(tmp_path))
    monkeypatch.setattr(route.settings, "demo", request.param)
    monkeypatch.setattr(route.settings, "sql_query", "SELECT 1 WHERE 1=1")
    monkeypatch.setattr(route.settings, "sql_query_not_have", "SELECT 1 WHERE 1=1")
    # No real email or HTML reporting in either mode.
    monkeypatch.setattr(route, "send_results_email", lambda **kwargs: None)
    monkeypatch.setattr(route, "generate_html_report", lambda *args, **kwargs: None)

    def run(frame, **overrides):
        # The same synthetic patients are represented in both database schemas.
        frame = frame.copy()
        if request.param == "yes":
            frame = frame.drop(columns=["DOB"], errors="ignore")
        else:
            frame = frame.drop(columns=["Year_of_Birth"], errors="ignore")
        monkeypatch.setattr(route, "fetch_from_db", lambda query, params: frame.copy())
        definition = {
            "title": "Synthetic",
            "gender": "ALL",
            "ageRange": {"min": 18, "max": 120},
            "ethnicity": "ALL",
            "timeRange": None,
            "mustHaveFindings": None,
            "mustNotHaveFindings": None,
        }
        definition.update(overrides)
        result = route.process_cohort(route.CohortDefinition.model_validate(definition))
        assert result is not None, (
            "process_cohort returned None, probably after catching an internal error. "
            "Inspect the exception in cohort_route.py rather than changing expected counts."
        )
        return result

    return run


def make_frame(patients=20, admissions=1, findings=1):
    records = []
    for i in range(patients):
        for admission in range(admissions):
            for finding in range(findings):
                records.append({
                    "subject_key": f"P{i:03d}",
                    "Gender": "Female" if i % 2 else "Male",
                    "Ethnicity": "Ethnicity A",
                    "DOB": f"{date.today().year - 35}-01-01",
                    "Year_of_Birth": date.today().year - 35,
                    "Adm_Dt": f"2026-{admission + 1:02d}-05",
                    "DiagCode": "111",
                    "Diagnosis": "Synthetic condition",
                    "DiagDt": f"2026-{finding + 1:02d}-10",
                })
    return pd.DataFrame(records, columns=[
        "subject_key", "Gender", "Ethnicity", "DOB", "Year_of_Birth", "Adm_Dt",
        "DiagCode", "Diagnosis", "DiagDt",
    ])


def finding_details(*pairs):
    """Build a valid mustHaveFindings payload from (code, display) pairs."""
    return [{
        "code": [], "display": None, "count": None,
        "codesWithDetails": [
            {"code": code, "display": display, "count": None}
            for code, display in pairs
        ],
    }]


@pytest.mark.parametrize("n,expected", [
    (1, 0), (9, 0), (10, 10), (11, 10), (14, 10),
    (16, 20), (20, 20), (24, 20), (26, 30),
])
def test_total_unique_patient_counts(execute, n, expected):
    result = execute(make_frame(n))
    assert result["total_patients"] == expected


@pytest.mark.parametrize("admissions,findings", [
    (1, 1), (2, 1), (1, 2), (2, 2), (3, 2),
])
def test_demographics_unique_across_multiple_rows(execute, admissions, findings):
    result = execute(make_frame(20, admissions, findings))
    assert result["total_patients"] == 20
    assert {row["gender"]: row["count"] for row in result["genderCounts"]} == {
        "Male": 10, "Female": 10,
    }
    assert result["ethnicityCounts"] == [{"ethnicity": "Ethnicity A", "count": 20}]
    assert next(row["count"] for row in result["ageGroups"] if row["range"] == "30-39") == 20


@pytest.mark.parametrize("n", [10, 20, 30])
def test_single_admission_per_patient_count(execute, n):
    result = execute(make_frame(n, 1, 1))
    assert result["admissions_by_month"][0]["count"] == n


@pytest.mark.parametrize("admissions,findings", [(1, 2), (2, 2), (3, 2)])
def test_admissions_not_multiplied_by_diagnosis_join(execute, admissions, findings):
    result = execute(make_frame(20, admissions, findings))
    assert sum(row["count"] for row in result["admissions_by_month"]) == 20 * admissions


@pytest.mark.parametrize("admissions,findings", [
    (1, 1), (2, 1), (1, 2), (2, 2), (3, 2),
])
def test_finding_occurrences_not_multiplied_by_admission_join(execute, admissions, findings):
    result = execute(
        make_frame(20, admissions, findings),
        mustHaveFindings=finding_details(("111", "Synthetic condition")),
    )
    assert result["diagnoses_included"][0]["code"] == "111"
    # Unique (patient, SNOMED code, diagnosis date), NOT unique patients per code.
    assert result["diagnoses_included"][0]["count"] == 20 * findings


@pytest.mark.parametrize("n", [1, 5, 9])
def test_small_cohort_suppresses_all_distributions(execute, n):
    result = execute(make_frame(n))
    assert result["total_patients"] == 0
    assert result["genderCounts"] == []
    assert result["ageGroups"] == []
    assert result["ethnicityCounts"] == []
    assert result["admissions_by_month"] == []


@pytest.mark.parametrize("n,expected", [(10, 10), (14, 10), (16, 20), (26, 30)])
def test_finding_records_rounded_when_included(execute, n, expected):
    result = execute(
        make_frame(n),
        mustHaveFindings=finding_details(("111", "Synthetic condition")),
    )
    assert result["diagnoses_included"][0]["count"] == expected


def test_zero_patients_returns_zero_payload(execute):
    result = execute(make_frame(0))
    assert result["total_patients"] == 0
    assert result["genderCounts"] == []
    assert result["ageGroups"] == []
    assert result["ethnicityCounts"] == []
    assert result["admissions_by_month"] == []


def test_codes_with_same_description_are_counted_separately(execute):
    frame = make_frame(20)
    other = frame.iloc[:10].copy()
    other["DiagCode"] = "222"
    # Deliberately the SAME description: grouping must use codes, not labels.
    other["Diagnosis"] = "Synthetic condition"
    frame = pd.concat([frame, other], ignore_index=True)

    result = execute(
        frame,
        mustHaveFindings=finding_details(
            ("111", "Synthetic condition"),
            ("222", "Synthetic condition"),
        ),
    )
    counts = {row["code"]: row["count"] for row in result["diagnoses_included"]}
    assert counts == {"111": 20, "222": 10}
    assert result["total_patients"] == 20


def test_repeated_rows_do_not_inflate_diagnosis_occurrences(execute):
    frame = make_frame(20, admissions=2, findings=2)
    frame = pd.concat([frame, frame], ignore_index=True)
    result = execute(
        frame,
        mustHaveFindings=finding_details(("111", "Synthetic condition")),
    )
    assert result["diagnoses_included"][0]["count"] == 40
    assert result["total_patients"] == 20


def test_selected_code_not_in_results_gets_zero(execute):
    result = execute(
        make_frame(20),
        mustHaveFindings=finding_details(
            ("111", "Synthetic condition"),
            ("999", "Absent condition"),
        ),
    )
    counts = {row["code"]: row["count"] for row in result["diagnoses_included"]}
    assert counts == {"111": 20, "999": 0}


def test_multiple_diagnosis_dates_same_patient_and_code(execute):
    result = execute(
        make_frame(20, admissions=1, findings=3),
        mustHaveFindings=finding_details(("111", "Synthetic condition")),
    )
    assert result["diagnoses_included"][0]["count"] == 60
    assert result["total_patients"] == 20

