"""Tests real process_cohort SQL assembly without any DB/FHIR/network access.
These verify generated SQL and parameter order, NOT database execution.
"""
import pandas as pd
import pytest
from app.routes import cohort_route as route

@pytest.fixture
def runner(monkeypatch, tmp_path):
    queries=[]
    monkeypatch.setattr(route.settings,'saved_searches',str(tmp_path))
    monkeypatch.setattr(route.settings,'demo','yes')
    # These are deliberately dummy SQL templates. fetch_from_db is mocked below,
    # so no SQL is executed and private schema/table names are not needed.
    monkeypatch.setattr(route.settings, 'sql_query', 'SELECT 1 WHERE 1=1')
    monkeypatch.setattr(route.settings, 'sql_query_not_have', 'SELECT 1 WHERE 1=1')
    def capture(query, params):
        queries.append((query,list(params)))
        return pd.DataFrame(columns=['subject_key','Gender','Ethnicity','Year_of_Birth','Adm_Dt','DiagCode','Diagnosis'])
    monkeypatch.setattr(route,'fetch_from_db',capture)
    def invoke(**overrides):
        data=dict(title='Synthetic',gender='ALL',ageRange={'min':18,'max':120},ethnicity='ALL',timeRange=None,mustHaveFindings=None,mustNotHaveFindings=None)
        data.update(overrides)
        payload=route.process_cohort(route.CohortDefinition.model_validate(data))
        assert queries, 'SQL was not submitted (check returned error)'
        return queries[-1][0],queries[-1][1],payload
    return invoke

def codes(*items,start=None,end=None):
    return {'code':[], 'display':None, 'count':None, 'codesWithDetails':[{'code':str(item),'display':f'Diagnosis {item}','count':None} for item in items], 'timeFrame':{'start':start,'end':end}}

@pytest.mark.parametrize('lower,upper',[(18,120),(18,18),(30,50),(40,40),(0,150),(120,121)])
def test_age_range_parameter_order(runner,lower,upper):
    sql,params,_=runner(ageRange={'min':lower,'max':upper})
    assert 'BETWEEN ? AND ?' in sql
    assert params==[lower,upper]

@pytest.mark.parametrize('gender,expected',[
    ('ALL',[]),([{'code':'1','display':'Male'}],['Male']),
    ([{'code':'2','display':'Female'}],['Female']),
    ([{'code':'1','display':'Male'},{'code':'2','display':'Female'}],['Male','Female'])
])
def test_gender_selection(runner,gender,expected):
    sql,params,_=runner(gender=gender)
    assert ('p.gender_display IN (' in sql)==bool(expected)
    assert params==[18,120]+expected

@pytest.mark.parametrize('ethnicity,expected',[
    ('ALL',[]),([{'code':'A','display':'White British'}],['White British']),
    ([{'code':'A','display':'White British'},{'code':'B','display':'Asian British'}],['White British','Asian British'])
])
def test_ethnicity_selection(runner,ethnicity,expected):
    sql,params,_=runner(ethnicity=ethnicity)
    assert ('p.ethnic_category_display IN (' in sql)==bool(expected)
    assert params==[18,120]+expected

@pytest.mark.parametrize('start,end',[(None,None),('2026-01-01',None),(None,'2026-12-31'),('2026-01-01','2026-12-31')])
def test_admission_date_selection(runner,start,end):
    sql,params,_=runner(timeRange={'start':start,'end':end})
    assert ('a.admit_datetime >= ?' in sql)==bool(start)
    assert ('a.admit_datetime <= ?' in sql)==bool(end)
    assert params==[18,120]+([start] if start else [])+([end] if end else [])

@pytest.mark.parametrize('items,expected',[
    ([codes('111')],['111']),([codes('111','222')],['111','222']),
    ([codes('111'),codes('222')],['111','222']),
    ([codes('111','222'),codes('333')],['111','222','333'])
])
def test_have_code_selection(runner,items,expected):
    sql,params,_=runner(mustHaveFindings=items)
    assert 'CAST(l.SNOMED_ConceptId AS VARCHAR(50))' in sql
    assert params==[18,120]+expected
    assert (' OR ' in sql)==(len(items)>1)

@pytest.mark.parametrize('start,end',[(None,None),('2025-01-01',None),(None,'2025-12-31'),('2025-01-01','2025-12-31')])
def test_have_diagnosis_dates(runner,start,end):
    sql,params,_=runner(mustHaveFindings=[codes('111',start=start,end=end)])
    assert ('c.condition_datetime >= ?' in sql)==bool(start)
    assert ('c.condition_datetime <= ?' in sql)==bool(end)
    assert params==[18,120,'111']+([start] if start else [])+([end] if end else [])

@pytest.mark.parametrize('items,expected',[
    ([codes('111')],['111']),([codes('111','222')],['111','222']),
    ([codes('111'),codes('222')],['111','222'])
])
def test_not_have_code_selection(runner,items,expected):
    sql,params,_=runner(mustNotHaveFindings=items)
    assert sql.count('NOT EXISTS (')==len(items)
    assert params==[18,120]+expected

@pytest.mark.parametrize('start,end',[(None,None),('2025-01-01',None),(None,'2025-12-31'),('2025-01-01','2025-12-31')])
def test_not_have_diagnosis_dates(runner,start,end):
    sql,params,_=runner(mustNotHaveFindings=[codes('111',start=start,end=end)])
    assert ('c2.condition_datetime >= ?' in sql)==bool(start)
    assert ('c2.condition_datetime <= ?' in sql)==bool(end)
    assert params==[18,120,'111']+([start] if start else [])+([end] if end else [])
