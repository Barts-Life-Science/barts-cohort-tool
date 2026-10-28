import asyncio
from unittest.mock import Mock
import pandas as pd
import pytest
from pydantic import ValidationError
from app.routes import cohort_route as route

@pytest.mark.parametrize('count,expected',[
    (-2,0),(0,0),(1,0),(9,0),(10,10),(11,10),(14,10),
    (16,20),(19,20),(20,20),(24,20),(26,30),(99,100),(105,100),
])
def test_disclosure_control(count,expected):
    assert route.anonymise_count(count)==expected

@pytest.mark.parametrize('count,threshold,expected',[
    (4,5,0),(5,5,0),(9,12,0),(12,12,10),(20,25,0),(25,25,20),
])
def test_disclosure_threshold(count,threshold,expected):
    assert route.anonymise_count(count,threshold)==expected

@pytest.mark.parametrize('field,missing',[
    ('title',True),('gender',True),('ageRange',True),('ethnicity',True),
])
def test_required_fields_rejected(definition,field,missing):
    data=definition.model_dump()
    data.pop(field)
    with pytest.raises(ValidationError): route.CohortDefinition.model_validate(data)

def test_optional_fields_can_be_null(definition):
    assert definition.timeRange is None
    assert definition.mustHaveFindings is None
    assert definition.mustNotHaveFindings is None

def test_gender_code_entries(definition):
    data=definition.model_dump()
    data['gender']=[{'code':'1','display':'Male'}]
    assert route.CohortDefinition.model_validate(data).gender[0].code=='1'

def test_age_range_accepts_model_fields(definition):
    assert (definition.ageRange.min,definition.ageRange.max)==(18,120)

def test_config_demo_true(monkeypatch):
    monkeypatch.setattr(route.settings,'demo','yes')
    assert route.get_config()=={'demo':True}

def test_config_demo_false(monkeypatch):
    monkeypatch.setattr(route.settings,'demo','no')
    assert route.get_config()=={'demo':False}

def test_snomed_display_happy_path(monkeypatch):
    monkeypatch.setattr(route.client,'search_snomed',Mock(return_value={'entry':[{'resource':{'display':'Example'}}]}))
    assert route.get_snomed_display('123456')=='Example'

def test_snomed_display_missing_entry(monkeypatch):
    monkeypatch.setattr(route.client, 'search_snomed', Mock(return_value={}), raising=False)
    assert route.get_snomed_display('123456')=='Unknown'

def test_snomed_display_exception(monkeypatch):
    monkeypatch.setattr(route.client, 'search_snomed', Mock(side_effect=RuntimeError('offline')), raising=False)
    assert route.get_snomed_display('123456')=='Unknown'

def test_db_connection_failure_raises_error(monkeypatch):
    monkeypatch.setattr(
        route.pyodbc,
        "connect",
        Mock(side_effect=ConnectionError("offline"))
    )

    with pytest.raises(ConnectionError, match="offline"):
        route.get_db_connection()

def test_db_connection_success(monkeypatch):
    connection=Mock()
    connect=Mock(return_value=connection)
    monkeypatch.setattr(route.pyodbc,'connect',connect)
    assert route.get_db_connection() is connection
    connect.assert_called_once_with(route.settings.dw_connection)

def test_fetch_from_db_empty_without_connection(monkeypatch):
    monkeypatch.setattr(route,'get_db_connection',lambda:None)
    assert route.fetch_from_db('SELECT 1',[]).empty

def test_fetch_from_db_multiple_batches_and_closes(monkeypatch):
    cursor=Mock()
    cursor.description=[('DOB',),('person_id',)]
    cursor.fetchmany.side_effect=[[('1984-06-15',1),('1990-03-20',2)], [('2000-09-10',3)], []]
    connection=Mock()
    connection.cursor.return_value=cursor
    monkeypatch.setattr(route,'get_db_connection',lambda:connection)
    frame=route.fetch_from_db('SELECT ?', [1])
    assert frame.shape==(3,2)
    assert list(frame.columns)==['DOB','person_id']
    assert frame['person_id'].tolist()==[1,2,3]
    cursor.execute.assert_called_once_with('SELECT ?',[1])
    assert all(c.args==(500,) for c in cursor.fetchmany.call_args_list)
    cursor.close.assert_called_once()
    connection.close.assert_called_once()

def test_fetch_from_db_zero_rows_keeps_columns(monkeypatch):
    cursor=Mock(description=[('person_id',)],fetchmany=Mock(return_value=[]))
    connection=Mock(cursor=Mock(return_value=cursor))
    monkeypatch.setattr(route,'get_db_connection',lambda:connection)
    frame=route.fetch_from_db('SELECT 1',[])
    assert frame.empty
    assert frame.columns.tolist()==['person_id']
    cursor.close.assert_called_once()
    connection.close.assert_called_once()

def test_fetch_from_db_sql_error_closes_connection(monkeypatch):
    cursor=Mock()
    cursor.execute.side_effect=RuntimeError('SQL failed')
    connection=Mock(cursor=Mock(return_value=cursor))
    monkeypatch.setattr(route,'get_db_connection',lambda:connection)
    with pytest.raises(RuntimeError,match='SQL failed'):
        route.fetch_from_db('bad query',[])
    cursor.close.assert_called_once()
    connection.close.assert_called_once()

def test_select_queues_job_in_production(monkeypatch,definition):
    queue=Mock()
    monkeypatch.setattr(route.settings,'demo','no')
    monkeypatch.setattr(route,'get_queue',lambda:queue)
    result=asyncio.run(route.run_select(definition))
    assert result['status']=='processing'
    queue.put.assert_called_once_with(definition.model_dump())

def test_select_direct_process_in_demo(monkeypatch,definition):
    process=Mock(return_value={'total':123})
    monkeypatch.setattr(route.settings,'demo','yes')
    monkeypatch.setattr(route,'process_cohort',process)
    assert asyncio.run(route.run_select(definition))=={'total':123}
    process.assert_called_once_with(definition)
