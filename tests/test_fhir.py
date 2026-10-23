import pytest
from app.services.fhir_client import is_snomed_code

@pytest.mark.parametrize('value', ['123456','123456789012345678',' 123456 '])
def test_valid_snomed_format(value):
    assert is_snomed_code(value)

@pytest.mark.parametrize('value', ['','12345','1234567890123456789','012345','ABCDEF','123 456','-123456'])
def test_invalid_snomed_format(value):
    assert not is_snomed_code(value)
