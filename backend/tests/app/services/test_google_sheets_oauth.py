"""The backend's Google Sheets OAuth flow (GOOGLE_SHEETS_OAUTH=backend), against
a fake Google: the authorization URL, the code exchange, the stored credential
(byte-compatible with what the actions executor reads), spreadsheet creation
and the error paths. No request leaves the process."""

import ast
import base64
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from loguru import logger
from pydantic import ValidationError

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services import google_sheets_oauth as sheets
from backend.config import settings
from backend.config.google_sheets_settings import GoogleSheetsSettings
from tests.app.sheets_helpers import (
    ACCESS_TOKEN,
    AUTH_URI,
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URL,
    REFRESH_TOKEN,
    SPREADSHEET_ID,
    TOKEN_URI,
    credential_dict,
    decrypt_credential,
    fake_google,  # noqa: F401 (fixture)
    sheets_client,  # noqa: F401 (fixture)
)

REPO = Path(__file__).resolve().parents[4]
EXECUTOR = REPO / "temporal/actions-executor"
GOOGLE_SERVICE = REPO / "integrations/google/googleform"
# The key order of the credential JSON the Google Forms service stored
# (GoogleCredentialResponse.dict()) and the actions executor reads.
CREDENTIAL_KEYS = [
    "token",
    "refresh_token",
    "token_uri",
    "client_id",
    "client_secret",
    "scopes",
    "expiry",
]


@pytest.fixture()
def service(sheets_client, fake_google):  # noqa: F811 (fixtures)
    return sheets.GoogleSheetsOAuth(container.crypto(), transport=fake_google.transport)


@pytest.fixture()
def logged():
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    yield lines
    logger.remove(sink)


def _state(user_id="user-1") -> str:
    return container.crypto().encrypt(
        json.dumps({"client_referer_uri": None, "user_id": user_id})
    )


def _stored(token="still-valid", expiry=None, **extra) -> str:
    expiry = expiry or datetime.utcnow() + timedelta(minutes=30)
    credential = {
        "token": token,
        "refresh_token": "stored-refresh-token",
        "token_uri": TOKEN_URI,
        "client_id": "stored-client-id",
        "client_secret": "stored-client-secret",
        "scopes": sheets.DRIVE_FILE_SCOPE,
        "expiry": expiry.strftime(sheets.CREDENTIAL_EXPIRY_FORMAT),
        **extra,
    }
    return container.crypto().encrypt(json.dumps(credential))


def _assert_nothing_secret(lines, *secrets):
    text = "\n".join(lines)
    for secret in secrets:
        assert secret not in text


class TestSwitch:
    def test_the_default_is_the_google_service(self):
        assert GoogleSheetsSettings.model_fields["SHEETS_OAUTH"].default == "google_service"

    def test_unset_reads_the_default(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SHEETS_OAUTH", raising=False)
        assert GoogleSheetsSettings().SHEETS_OAUTH == "google_service"

    def test_values_are_normalised(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEETS_OAUTH", " Backend ")
        assert GoogleSheetsSettings().SHEETS_OAUTH == "backend"

    def test_an_unknown_value_refuses_to_start(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEETS_OAUTH", "both")
        with pytest.raises(ValidationError):
            GoogleSheetsSettings()

    def test_the_backend_reads_the_sign_in_client(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id-from-env")
        monkeypatch.setenv("GOOGLE_TOKEN_URI", "https://token.example.test/t")
        config = GoogleSheetsSettings()
        assert config.CLIENT_ID == "id-from-env"
        assert config.TOKEN_URI == "https://token.example.test/t"


class TestAuthorizationUrl:
    def test_asks_for_drive_file_only_offline_with_consent(self, service):
        state = _state()
        url = urlparse(service.authorization_url(state))
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        assert f"{url.scheme}://{url.netloc}{url.path}" == AUTH_URI
        verifier = sheets.pkce_code_verifier(state)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        assert params == {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URL,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/drive.file",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "false",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }

    def test_the_verifier_is_a_valid_pkce_verifier_bound_to_the_state(self):
        a, b = sheets.pkce_code_verifier("state-a"), sheets.pkce_code_verifier("state-b")
        assert a != b and a == sheets.pkce_code_verifier("state-a")
        assert len(a) == 43 and set(a) <= set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
        )

    @pytest.mark.parametrize("missing", ["CLIENT_ID", "CLIENT_SECRET"])
    def test_refuses_without_the_sign_in_client(
        self, service, sheets_client, monkeypatch, missing  # noqa: F811
    ):
        monkeypatch.setattr(sheets_client, missing, "")
        with pytest.raises(HTTPException) as refused:
            service.authorization_url(_state())
        assert refused.value.status_code == 503


class TestExchange:
    async def test_exchanges_the_code_with_the_pkce_verifier(self, service, fake_google):
        state = _state()
        await service.exchange_code(code="the-code", state=state)

        assert fake_google.token_requests() == [
            {
                "code": "the-code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URL,
                "grant_type": "authorization_code",
                "code_verifier": sheets.pkce_code_verifier(state),
            }
        ]

    async def test_stores_the_credential_in_the_executor_format(self, service):
        before = datetime.utcnow()
        ciphertext = await service.exchange_code(code="code", state=_state())
        after = datetime.utcnow()

        plaintext = decrypt_credential(ciphertext)
        credential = json.loads(plaintext)
        # byte for byte what json.dumps(GoogleCredentialResponse(...).dict()) gave
        assert list(credential) == CREDENTIAL_KEYS
        assert plaintext == json.dumps(credential)
        assert credential == {
            "token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
            "token_uri": TOKEN_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scopes": "https://www.googleapis.com/auth/drive.file",
            "expiry": credential["expiry"],
        }
        expiry = datetime.strptime(credential["expiry"], "%Y-%m-%dT%H:%M:%S.%fZ")
        assert before + timedelta(seconds=3598) <= expiry <= after + timedelta(seconds=3600)

    async def test_the_executor_can_read_it(self, service):
        """What temporal/actions-executor does with the stored value: Fernet
        decrypt with AUTH_AES_HEX_KEY, json.loads, parse the expiry with its
        format and split the scopes string (utilities/actions.py
        append_in_sheet, utilities/google_service.py dict_to_credential)."""
        ciphertext = await service.exchange_code(code="code", state=_state())

        # the executor's crypto is a plain Fernet over AUTH_AES_HEX_KEY
        credential = json.loads(
            Fernet(settings.auth_settings.AES_HEX_KEY).decrypt(ciphertext).decode()
        )
        datetime.strptime(credential["expiry"], _executor_datetime_format())
        assert isinstance(credential["scopes"], str)
        credential["scopes"] = credential.get("scopes").split(" ")[1:]
        assert set(credential) == set(CREDENTIAL_KEYS)

    async def test_a_response_without_scope_grants_the_requested_one(
        self, service, fake_google
    ):
        del fake_google.token_body["scope"]
        ciphertext = await service.exchange_code(code="code", state=_state())
        assert credential_dict(ciphertext)["scopes"] == sheets.DRIVE_FILE_SCOPE

    async def test_refuses_when_drive_file_was_not_granted(self, service, fake_google):
        fake_google.token_body["scope"] = "openid email"
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="code", state=_state())
        assert refused.value.status_code == 403

    async def test_refuses_without_a_refresh_token(self, service, fake_google):
        del fake_google.token_body["refresh_token"]
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="code", state=_state())
        assert refused.value.status_code == 417

    @pytest.mark.parametrize("missing", ["access_token", "expires_in"])
    async def test_refuses_without_token_or_expiry(self, service, fake_google, missing):
        del fake_google.token_body[missing]
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="code", state=_state())
        assert refused.value.status_code == 417

    @pytest.mark.parametrize(
        "status,error,message",
        [
            (400, "invalid_grant", "Invalid oauth2 grant!"),
            (401, "invalid_client", "Oauth invalid client error!"),
            (400, "redirect_uri_mismatch", "Could not fetch oauth token!"),
            (500, None, "Could not fetch oauth token!"),
        ],
    )
    async def test_google_refusals(
        self, service, fake_google, logged, status, error, message
    ):
        fake_google.token_status = status
        fake_google.token_body = (
            {"error": error, "error_description": "secret detail"} if error else {}
        )
        state = _state()
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="the-code", state=state)
        assert refused.value.status_code == 417
        assert refused.value.content == message
        _assert_nothing_secret(logged, "the-code", "secret detail", CLIENT_SECRET, state)

    @pytest.mark.parametrize(
        "failure,status",
        [
            (lambda r: httpx.ReadTimeout("slow", request=r), 504),
            (lambda r: httpx.ConnectError("down", request=r), 502),
        ],
    )
    async def test_google_unreachable(self, service, fake_google, failure, status):
        fake_google.fail_with = failure
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="code", state=_state())
        assert refused.value.status_code == status

    async def test_an_expired_state_is_refused_before_the_exchange(
        self, service, fake_google
    ):
        old = Fernet.encrypt_at_time(
            container.crypto(),
            json.dumps({"user_id": "user-1"}).encode(),
            int(time.time()) - sheets.STATE_MAX_AGE_SECONDS - 60,
        ).decode()
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="code", state=old)
        assert refused.value.status_code == 400
        assert fake_google.requests == []

    async def test_a_forged_state_is_refused_before_the_exchange(
        self, service, fake_google
    ):
        forged = Fernet(Fernet.generate_key()).encrypt(b"{}").decode()
        with pytest.raises(HTTPException) as refused:
            await service.exchange_code(code="code", state=forged)
        assert refused.value.status_code == 400
        assert fake_google.requests == []

    async def test_logs_carry_no_token(self, service, logged):
        await service.exchange_code(code="the-code", state=_state())
        _assert_nothing_secret(logged, ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_SECRET, "the-code")


class TestCreateSpreadsheet:
    async def test_creates_it_with_the_stored_token(self, service, fake_google, logged):
        sheet_id = await service.create_spreadsheet("Customer feedback", _stored())

        assert sheet_id == SPREADSHEET_ID
        [request] = fake_google.requests
        assert request.url.params["fields"] == "spreadsheetId"
        assert request.headers["Authorization"] == "Bearer still-valid"
        assert json.loads(request.content) == {
            "properties": {"title": "Customer feedback"}
        }
        _assert_nothing_secret(logged, "Customer feedback", "still-valid")

    async def test_refreshes_an_expired_token_first(self, service, fake_google, logged):
        stored = _stored(expiry=datetime.utcnow() - timedelta(minutes=5))

        assert await service.create_spreadsheet("Title", stored) == SPREADSHEET_ID

        assert fake_google.token_requests() == [
            {
                "client_id": "stored-client-id",
                "client_secret": "stored-client-secret",
                "refresh_token": "stored-refresh-token",
                "grant_type": "refresh_token",
            }
        ]
        [created] = fake_google.sheets_requests()
        assert created.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        _assert_nothing_secret(logged, ACCESS_TOKEN, "stored-refresh-token")

    async def test_a_legacy_credential_still_creates_the_sheet(self, service):
        legacy = _stored(
            scopes="https://www.googleapis.com/auth/spreadsheets "
            "https://www.googleapis.com/auth/drive"
        )
        assert await service.create_spreadsheet("Title", legacy) == SPREADSHEET_ID

    @pytest.mark.parametrize(
        "status,expected", [(401, 401), (403, 401), (404, 503), (500, 503)]
    )
    async def test_google_refusals(self, service, fake_google, status, expected):
        fake_google.sheets_status = status
        fake_google.sheets_body = {"error": {"status": "PERMISSION_DENIED"}}
        with pytest.raises(HTTPException) as refused:
            await service.create_spreadsheet("Title", _stored())
        assert refused.value.status_code == expected

    async def test_an_answer_without_an_id_is_an_error(self, service, fake_google):
        fake_google.sheets_body = {}
        with pytest.raises(HTTPException) as refused:
            await service.create_spreadsheet("Title", _stored())
        assert refused.value.status_code == 503

    async def test_timeout(self, service, fake_google):
        fake_google.fail_with = lambda r: httpx.ReadTimeout("slow", request=r)
        with pytest.raises(HTTPException) as refused:
            await service.create_spreadsheet("Title", _stored())
        assert refused.value.status_code == 504

    async def test_an_unreadable_credential_is_refused(self, service, fake_google):
        with pytest.raises(HTTPException) as refused:
            await service.create_spreadsheet("Title", "not-a-credential")
        assert refused.value.status_code == 401
        assert fake_google.requests == []

    async def test_an_expired_token_without_refresh_token_is_refused(
        self, service, fake_google
    ):
        stored = _stored(
            expiry=datetime.utcnow() - timedelta(minutes=5), refresh_token=None
        )
        with pytest.raises(HTTPException) as refused:
            await service.create_spreadsheet("Title", stored)
        assert refused.value.status_code == 401
        assert fake_google.requests == []


# ---------------------------------------------------------------- golden


def _assigned_string(path: Path, name: str) -> str:
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    raise AssertionError(f"{name} not found in {path}")


def _executor_datetime_format() -> str:
    path = EXECUTOR / "models/date.py"
    if not path.is_file():
        return "%Y-%m-%dT%H:%M:%S.%fZ"
    return _assigned_string(path, "GOOGLE_DATETIME_FORMAT")


def test_the_expiry_format_is_the_executors():
    if not (EXECUTOR / "models/date.py").is_file():
        pytest.skip("needs the whole repository")
    assert sheets.CREDENTIAL_EXPIRY_FORMAT == _executor_datetime_format()


def test_the_executor_still_splits_the_scopes_string():
    """The executor turns ``scopes`` into a list itself; a stored list would
    break it. If this changes, so must the stored format."""
    path = EXECUTOR / "utilities/actions.py"
    if not path.is_file():
        pytest.skip("needs the whole repository")
    assert 'credential.get("scopes").split(" ")' in path.read_text()


def test_the_key_order_is_the_google_services():
    path = GOOGLE_SERVICE / "app/models/oauth_credential.py"
    if not path.is_file():
        pytest.skip("needs the whole repository")
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ClassDef) and node.name == "GoogleCredentialResponse":
            fields = [
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            ]
            assert fields == CREDENTIAL_KEYS
            return
    raise AssertionError("GoogleCredentialResponse not found")
