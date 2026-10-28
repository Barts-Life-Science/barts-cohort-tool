import asyncio
from unittest.mock import Mock
import pytest
from app.routes import snomed_route as route

@pytest.mark.parametrize('code', ['123456','<123456','(<<123456 OR <789012)'])
def test_include_inactive_appends_history(code):
    assert route.include_inactive(code)==code+' {{ %2B HISTORY-MAX }}'

@pytest.mark.parametrize('endpoint,term,ecl',[
    (route.search_snomed_findings,'diabetes','<404684003'),
    (route.search_snomed_procedures,'scan','<71388002'),
])
def test_category_search(monkeypatch,endpoint,term,ecl):
    call=Mock(return_value={'found':True})
    monkeypatch.setattr(
    route.client,
    'search_snomed',
    call,
    raising=False
)
    assert asyncio.run(endpoint(term))=={'found':True}
    call.assert_called_once_with(ecl,term)

def test_snomed_search_expands_history(monkeypatch):
    call=Mock(return_value={'found':True})
    monkeypatch.setattr(
    route.client,
    'search_snomed',
    call,
    raising=False
)
    asyncio.run(route.search_snomed('<123456','test'))
    call.assert_called_once_with('(<123456) {{ %2B HISTORY-MAX }}','test')

def test_count_descendants(monkeypatch):
    call=Mock(return_value={'total':10})
    monkeypatch.setattr(
    route.client,
    'search_snomed',
    call,
    raising=False
)
    assert asyncio.run(route.snomed_count_descendants('123456'))=={'total':10}
    call.assert_called_once_with('<<123456 {{ %2B HISTORY-MAX }}','',1)

def test_lookup(monkeypatch):
    call=Mock(return_value={'display':'Example'})
    monkeypatch.setattr(route.client,'search_snomed_description_id',call,raising=False)
    assert asyncio.run(route.lookup_snomed('123456'))=={'display':'Example'}
    call.assert_called_once_with('123456')
