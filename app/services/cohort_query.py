"""
Cohort counts against the gold-fed Azure SQL tables.

The SNOMED COHORT BROWSER ADF pipeline loads three tables from 4_prod.gold into
the `cohort` schema (see README):

    cohort.person     one row per person: birth_year, NHS gender/ethnic codes
    cohort.condition  one row per coded condition event: snomed_code, condition_datetime
    cohort.admission  one row per inpatient spell: admit_datetime, discharge_datetime

Rows carry gold's record_status; only 'active' rows are counted. All
aggregation happens in SQL: the matching persons are inserted into a
#cohort temp table on the connection, and each chart is a GROUP BY over it.
Disclosure control is applied by the caller.
"""

from datetime import datetime

import pyodbc

from app.config import settings

ACTIVE = "'active'"


def _to_date(value):
    """Frontend dates come from <input type="date"> as YYYY-MM-DD."""
    if not value:
        return None
    return datetime.fromisoformat(str(value)[:10]).date()


def _blocks(filters):
    """[{codes, start, end}] -> (block rows, code rows) for the temp tables."""
    block_rows, code_rows = [], []
    for block_id, f in enumerate(filters, start=1):
        block_rows.append((block_id, _to_date(f["start"]), _to_date(f["end"])))
        for code in sorted({str(c).strip() for c in f["codes"] if str(c).strip()}):
            code_rows.append((block_id, code))
    return block_rows, code_rows


def _condition_match(prefix, person_ref):
    """Correlated predicate: an active condition for person_ref matching any block in #<prefix>_*."""
    s = settings.cohort_schema
    return f"""EXISTS (
            SELECT 1
            FROM #{prefix}_codes bc
            JOIN #{prefix}_blocks bb ON bb.block_id = bc.block_id
            JOIN {s}.condition c ON c.snomed_code = bc.snomed_code AND c.person_id = {person_ref}
            WHERE c.record_status = {ACTIVE}
              AND (bb.start_dt IS NULL OR c.condition_datetime >= bb.start_dt)
              AND (bb.end_dt IS NULL OR c.condition_datetime < DATEADD(day, 1, bb.end_dt))
        )"""


def _load_blocks(cursor, prefix, filters):
    block_rows, code_rows = _blocks(filters)
    cursor.execute(f"CREATE TABLE #{prefix}_blocks (block_id INT PRIMARY KEY, start_dt DATE NULL, end_dt DATE NULL)")
    cursor.execute(
        f"CREATE TABLE #{prefix}_codes (block_id INT NOT NULL, snomed_code VARCHAR(20) NOT NULL, "
        f"PRIMARY KEY (snomed_code, block_id))"
    )
    if block_rows:
        cursor.executemany(f"INSERT INTO #{prefix}_blocks VALUES (?, ?, ?)", block_rows)
    if code_rows:
        cursor.executemany(f"INSERT INTO #{prefix}_codes VALUES (?, ?)", code_rows)


def _admit_window(alias, admit_start, admit_end):
    """Admission-date predicates (end date inclusive) and their params."""
    where, params = [], []
    if admit_start:
        where.append(f"{alias}.admit_datetime >= ?")
        params.append(admit_start)
    if admit_end:
        where.append(f"{alias}.admit_datetime < DATEADD(day, 1, ?)")
        params.append(admit_end)
    return "".join(f"\n              AND {w}" for w in where), params


def build_cohort_sql(min_age, max_age, gender_codes, ethnicity_codes,
                     admit_start, admit_end, has_must_have, has_must_not):
    """Return (sql, params) that fills #cohort with the matching persons."""
    s = settings.cohort_schema
    where = [
        f"p.record_status = {ACTIVE}",
        "(YEAR(GETDATE()) - p.birth_year) BETWEEN ? AND ?",
    ]
    params = [min_age, max_age]

    if gender_codes:
        where.append(f"p.gender_code IN ({', '.join(['?'] * len(gender_codes))})")
        params.extend(gender_codes)

    if ethnicity_codes:
        where.append(f"p.ethnic_category_code IN ({', '.join(['?'] * len(ethnicity_codes))})")
        params.extend(ethnicity_codes)

    if admit_start or admit_end:
        window, window_params = _admit_window("a", admit_start, admit_end)
        where.append(f"""EXISTS (
            SELECT 1 FROM {s}.admission a
            WHERE a.person_id = p.person_id
              AND a.record_status = {ACTIVE}{window}
        )""")
        params.extend(window_params)

    if has_must_have:
        where.append(_condition_match("have", "p.person_id"))

    if has_must_not:
        where.append("NOT " + _condition_match("not", "p.person_id"))

    sql = (
        "INSERT INTO #cohort (person_id, birth_year, gender_display, ethnic_category_display)\n"
        "SELECT p.person_id, p.birth_year, p.gender_display, p.ethnic_category_display\n"
        f"FROM {s}.person p\n"
        "WHERE " + "\n  AND ".join(where)
    )
    return sql, params


def _rows(cursor, sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchall()


def run_cohort_query(min_age, max_age, gender_codes, ethnicity_codes,
                     admit_start, admit_end, musthave_filters, mustnot_filters):
    """
    Count the cohort and its breakdowns. Returns raw (un-anonymised) counts:

        sql                     the #cohort statement, for the saved-search record
        total_patients          persons in the cohort
        total_records           active admissions of those persons (in the admission window, if set)
        age_min, age_max        None when the cohort is empty
        gender_counts           [(gender_display, n)]
        ethnicity_counts        [(ethnic_category_display, n)]
        ages                    [(age, n)]
        admissions_by_month     [(YYYY-MM, n)]
        diagnosis_counts        [(snomed_code, condition records)] for the must-have codes
    """
    admit_start = _to_date(admit_start)
    admit_end = _to_date(admit_end)
    s = settings.cohort_schema

    cohort_sql, cohort_params = build_cohort_sql(
        min_age, max_age, gender_codes, ethnicity_codes, admit_start, admit_end,
        bool(musthave_filters), bool(mustnot_filters),
    )

    conn = pyodbc.connect(settings.dw_connection)
    try:
        cursor = conn.cursor()
        if musthave_filters:
            _load_blocks(cursor, "have", musthave_filters)
        if mustnot_filters:
            _load_blocks(cursor, "not", mustnot_filters)

        print(">>> BUILDING #cohort")
        # Created unparameterised so it lives on the session: parameterised statements run
        # through sp_prepexec, and a temp table created inside one is dropped when it returns.
        cursor.execute(
            "CREATE TABLE #cohort (person_id BIGINT PRIMARY KEY, birth_year INT NULL, "
            "gender_display NVARCHAR(64) NULL, ethnic_category_display NVARCHAR(64) NULL)"
        )
        cursor.execute(cohort_sql, cohort_params)

        total_patients, age_min, age_max = _rows(
            cursor,
            "SELECT COUNT(*), MIN(YEAR(GETDATE()) - birth_year), MAX(YEAR(GETDATE()) - birth_year) FROM #cohort",
        )[0]
        print(f">>> COHORT SIZE {total_patients:,}")

        gender_counts = _rows(cursor, "SELECT gender_display, COUNT(*) FROM #cohort GROUP BY gender_display")
        ethnicity_counts = _rows(
            cursor, "SELECT ethnic_category_display, COUNT(*) FROM #cohort GROUP BY ethnic_category_display"
        )
        ages = _rows(
            cursor,
            "SELECT YEAR(GETDATE()) - birth_year AS age, COUNT(*) FROM #cohort GROUP BY YEAR(GETDATE()) - birth_year",
        )

        window, window_params = _admit_window("a", admit_start, admit_end)
        admission_months = _rows(
            cursor,
            f"""SELECT CONVERT(CHAR(7), a.admit_datetime, 126) AS month_year, COUNT(*)
            FROM #cohort k
            JOIN {s}.admission a ON a.person_id = k.person_id
            WHERE a.record_status = {ACTIVE}{window}
            GROUP BY CONVERT(CHAR(7), a.admit_datetime, 126)""",
            window_params,
        )
        total_records = sum(n for _, n in admission_months)
        admissions_by_month = sorted((m, n) for m, n in admission_months if m is not None)

        diagnosis_counts = []
        if musthave_filters:
            diagnosis_counts = _rows(
                cursor,
                f"""SELECT c.snomed_code, COUNT(*)
                FROM #cohort k
                JOIN {s}.condition c ON c.person_id = k.person_id
                WHERE c.record_status = {ACTIVE}
                  AND EXISTS (
                      SELECT 1
                      FROM #have_codes bc
                      JOIN #have_blocks bb ON bb.block_id = bc.block_id
                      WHERE bc.snomed_code = c.snomed_code
                        AND (bb.start_dt IS NULL OR c.condition_datetime >= bb.start_dt)
                        AND (bb.end_dt IS NULL OR c.condition_datetime < DATEADD(day, 1, bb.end_dt))
                  )
                GROUP BY c.snomed_code""",
            )
    finally:
        print(">>> CLOSING SQL CONNECTION")
        conn.close()

    return {
        "sql": cohort_sql,
        "total_patients": total_patients,
        "total_records": total_records,
        "age_min": age_min,
        "age_max": age_max,
        "gender_counts": [tuple(r) for r in gender_counts],
        "ethnicity_counts": [tuple(r) for r in ethnicity_counts],
        "ages": [tuple(r) for r in ages],
        "admissions_by_month": admissions_by_month,
        "diagnosis_counts": [tuple(r) for r in diagnosis_counts],
    }
