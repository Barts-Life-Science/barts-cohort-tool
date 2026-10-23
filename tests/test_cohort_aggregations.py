"""Synthetic, deterministic result checks. No patient data or DB access."""
import pandas as pd
import pytest
from app.routes import cohort_route as route

@pytest.fixture
def execute(monkeypatch,tmp_path):
    monkeypatch.setattr(route.settings,'saved_searches',str(tmp_path))
    monkeypatch.setattr(route.settings,'demo','yes')
    monkeypatch.setattr(route.settings,'sql_query','SELECT 1 WHERE 1=1')
    monkeypatch.setattr(route.settings,'sql_query_not_have','SELECT 1 WHERE 1=1')
    def run(frame,**overrides):
        monkeypatch.setattr(route,'fetch_from_db',lambda q,p:frame.copy())
        d=dict(title='Synthetic',gender='ALL',ageRange={'min':18,'max':120},ethnicity='ALL',timeRange=None,mustHaveFindings=None,mustNotHaveFindings=None)
        d.update(overrides)
        return route.process_cohort(route.CohortDefinition.model_validate(d))
    return run

def make_frame(patients=20,admissions=1,findings=1):
    records=[]
    for i in range(patients):
        for admission in range(admissions):
            for finding in range(findings):
                records.append(dict(subject_key=f'P{i:03d}',Gender='Female' if i%2 else 'Male',
                    Ethnicity='Ethnicity A',Year_of_Birth=1990,
                    Adm_Dt=f'2026-0{admission+1}-05',DiagCode='111',Diagnosis='Synthetic condition'))
    return pd.DataFrame(records)

@pytest.mark.parametrize('n,expected',[(1,0),(9,0),(10,10),(11,10),(14,10),(16,20),(20,20),(24,20),(26,30)])
def test_total_unique_patient_counts(execute,n,expected):
    result=execute(make_frame(n))
    assert result['total_patients']==expected

@pytest.mark.parametrize('admissions,findings',[(1,1),(2,1),(1,2),(2,2),(3,2)])
def test_demographics_unique_across_multiple_rows(execute,admissions,findings):
    result=execute(make_frame(20,admissions,findings))
    assert result['total_patients']==20
    assert {row['gender']:row['count'] for row in result['genderCounts']}=={'Male':10,'Female':10}
    assert result['ethnicityCounts']==[{'ethnicity':'Ethnicity A','count':20}]
    assert next(row['count'] for row in result['ageGroups'] if row['range']=='30-39')==20

@pytest.mark.parametrize('n', [10,20,30])
def test_single_admission_per_patient_count(execute,n):
    result=execute(make_frame(n,1,1))
    assert result['admissions_by_month'][0]['count']==n

@pytest.mark.parametrize('admissions,findings',[(1,2),(2,2),(3,2)])
@pytest.mark.xfail(strict=True,reason='Current implementation counts joined rows rather than distinct admissions; requires admission ID or reliable deduplication')
def test_admissions_not_multiplied_by_diagnosis_join(execute,admissions,findings):
    result=execute(make_frame(20,admissions,findings))
    assert sum(row['count'] for row in result['admissions_by_month'])==20*admissions

@pytest.mark.parametrize('admissions,findings',[(1,1),(2,1),(2,2)])
@pytest.mark.xfail(strict=True,reason='Current implementation counts joined rows; cannot distinguish true finding records from join multiplication without source record IDs')
def test_finding_records_not_multiplied_by_admission_join(execute,admissions,findings):
    result=execute(make_frame(20,admissions,findings,mustHaveFindings=[{'code':[],'display':None,'count':None,'codesWithDetails':[{'code':'111','display':'Synthetic condition','count':None}]}]))
    assert result['diagnoses_included'][0]['count']==20*findings

@pytest.mark.parametrize('n', [1,5,9])
def test_small_cohort_suppresses_all_distributions(execute,n):
    result=execute(make_frame(n))
    assert result['total_patients']==0
    assert result['genderCounts']==[]
    assert result['ageGroups']==[]
    assert result['ethnicityCounts']==[]
    assert result['admissions_by_month']==[]

@pytest.mark.parametrize('n,expected',[(10,10),(14,10),(16,20),(26,30)])
def test_finding_records_rounded_when_included(execute,n,expected):
    result=execute(make_frame(n),mustHaveFindings=[{'code':[],'display':None,'count':None,'codesWithDetails':[{'code':'111','display':'Synthetic condition','count':None}]}])
    assert result['diagnoses_included'][0]['count']==expected

@pytest.mark.xfail(strict=True,reason='Empty DataFrame handling raises before suppression rather than returning zero cohort')
def test_zero_patients_returns_zero_payload(execute):
    assert execute(make_frame(0))['total_patients']==0
