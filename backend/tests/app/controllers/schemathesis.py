import schemathesis
from schemathesis.checks import not_a_server_error
from hypothesis import settings

schema = schemathesis.from_uri(
    # "https://bettercollected-admin.sireto.dev/api/v1/openapi.json"
    "http://localhost:8000/api/v1/openapi.json"
)


@schema.parametrize()
@settings(max_examples=100)
def test_api(case):
    response = case.call()
    case.validate_response(response)
