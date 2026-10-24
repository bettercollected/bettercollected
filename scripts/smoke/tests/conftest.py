import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

FIXTURES = HERE / "fixtures"

# Made-up values shaped like the real ones; none of them works anywhere.
API_KEY = "bc_" + "0123456789abcdef" * 4
APP_PASSWORD = "abcd efgh ijkl mnop"
REFRESH_TOKEN = "1//0gFAKEFAKEFAKErefreshTokenForTests"
CLIENT_SECRET = "GOCSPX-fake-client-secret-for-tests"


@pytest.fixture
def base_env():
    return {
        "SMOKE_APP_URL": "https://admin.example.com",
        "SMOKE_API_KEY": API_KEY,
        "SMOKE_MAILBOX": "smoke@gmail.com",
        "SMOKE_WORKSPACE_ID": "smoke-test",
        "SMOKE_CUSTOM_DOMAIN": "forms.example.org",
        "SMOKE_GOOGLE_FORM_ID": "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF",
    }


@pytest.fixture
def code_mail_bytes():
    return (FIXTURES / "code_mail.eml").read_bytes()
