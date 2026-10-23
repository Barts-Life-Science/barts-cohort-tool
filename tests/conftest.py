"""Isolated unit-test setup; never contacts the production database/FHIR endpoint."""
import os
import sys
import types
from pathlib import Path
from unittest.mock import Mock
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENV = {
    'FHIR_API_AUTH_SERVER':'https://invalid.example/token',
    'FHIR_API_URL':'https://invalid.example/fhir',
    'FHIR_API_CLIENT_ID':'test-client',
    'FHIR_API_CLIENT_SECRET':'test-secret',
    'DW_CONNECTION':'DRIVER={mock};SERVER=invalid.example',
    'SAVED_SEARCHES':'/tmp/pct_test_saved',
    'SQL_QUERY':'SELECT 1',
    'SQL_QUERY_NOT_HAVE':'SELECT 1',
    'SENDER_EMAIL':'test@example.invalid',
    'SMTP_SERVER':'invalid.example',
    'SMTP_PORT':'25',
    'APP_PASSWORD':'test',
    'FAILURE_EMAIL':'test@example.invalid',
    'DEMO':'no',
}
for name, value in ENV.items():
    os.environ.setdefault(name, value)

# Mock the FHIR object constructor before route import, which otherwise starts
# a token network request and a forever-running refresh thread.
import app.services.fhir_client as fhir_client
fhir_client.FHIRClient = Mock(return_value=Mock())

# The route imports an email module with optional report dependencies.
# Keep module import side-effect free; each test mocks its own collaborators.
email_mod = types.ModuleType('app.services.email_utils')
email_mod.send_results_email = Mock()
email_mod.generate_html_report = Mock()
sys.modules['app.services.email_utils'] = email_mod

# pyodbc/persistqueue should be installed on the deployment environment.
# Provide minimal stand-ins in lightweight test-only environments.
try:
    import pyodbc  # noqa: F401
except ImportError:
    db_stub = types.ModuleType('pyodbc')
    db_stub.connect = Mock(side_effect=RuntimeError('Database access disabled in tests'))
    sys.modules['pyodbc'] = db_stub
try:
    import persistqueue  # noqa: F401
except ImportError:
    pq = types.ModuleType('persistqueue')
    exc = types.ModuleType('persistqueue.exceptions')
    class Empty(Exception):
        pass
    exc.Empty = Empty
    pq.exceptions = exc
    pq.SQLiteAckQueue = type("SQLiteAckQueue", (), {})
    sys.modules['persistqueue'] = pq
    sys.modules['persistqueue.exceptions'] = exc

@pytest.fixture
def definition():
    from app.routes.cohort_route import CohortDefinition
    return CohortDefinition.model_validate({
        'title': 'Demo study', 'gender':'ALL',
        'ageRange': {'min':18,'max':120}, 'ethnicity':'ALL',
        'timeRange':None, 'mustHaveFindings':None, 'mustNotHaveFindings':None,
    })
