"""Proof that a respondent's page showed the AI insights notice (#752).

A form with "Allow AI insights on responses" on shows respondents a notice
naming the AI provider. Whether a given respondent saw it cannot be inferred
from the submission time: someone who loaded the form before the setting was
turned on and submitted afterwards never saw it. So the public form fetch
hands out a signed token stating that the notice was shown, for which form,
provider and provider name, under which "allowed since" moment, and when; the
form page sends it back with the submission, and only a valid token that
still matches the form's current setting stamps the response
(``ai_notice_shown_at`` / ``ai_notice_provider_name``). Insights analyse only
stamped responses.

- **Signed** with HMAC-SHA256 under a key derived from the backend's
  ``AUTH_JWT_SECRET`` (a separate purpose label, so the token is never a
  valid JWT signature and vice versa). Without that secret no token is
  issued or accepted: nothing is analysed (fail closed).
- **Bound** to the workspace, the form id, the provider id and name, and the
  setting's ``ai_insights_enabled_at``: turning the setting off and on again
  (or a provider change, which needs a renewal) invalidates older tokens.
- **Valid for 24 hours** after the page loaded (``TOKEN_TTL``): long enough
  for a respondent who leaves the form open for a working day; a submission
  after that is stored normally but never analysed.
"""

import base64
import datetime as dt
import hashlib
import hmac
import json
from typing import Optional

from backend.config import settings

TOKEN_TTL = dt.timedelta(hours=24)
# a token from a server whose clock runs slightly ahead is still accepted
CLOCK_SKEW = dt.timedelta(minutes=2)
MAX_TOKEN_LENGTH = 2048
_VERSION = "v1"
_PURPOSE = b"bettercollected/ai-insights-notice-token/v1"


def _key() -> Optional[bytes]:
    secret = settings.auth_settings.JWT_SECRET
    if not secret:
        return None
    return hmac.new(secret.encode("utf-8"), _PURPOSE, hashlib.sha256).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _ms(value: dt.datetime) -> int:
    """Milliseconds since the epoch: what both stores keep of a timestamp."""
    return int(_utc(value).timestamp() * 1000)


def _sign(key: bytes, payload: str) -> str:
    return _b64(hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest())


def _claims(
    workspace_id, form_id, provider: str, provider_name: str, enabled_at
) -> dict:
    return {
        "w": str(workspace_id),
        "f": str(form_id),
        "p": provider,
        "n": provider_name,
        "e": _ms(enabled_at),
    }


def issue_token(
    *,
    workspace_id,
    form_id,
    provider: str,
    provider_name: str,
    enabled_at: dt.datetime,
    now: Optional[dt.datetime] = None,
) -> Optional[str]:
    """A token saying the notice for ``provider_name`` was shown now, or None
    when the server has no secret to sign it with."""
    key = _key()
    if key is None:
        return None
    issued = _utc(now or dt.datetime.now(dt.timezone.utc))
    claims = _claims(workspace_id, form_id, provider, provider_name, enabled_at)
    claims["i"] = _ms(issued)
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    body = f"{_VERSION}.{payload}"
    return f"{body}.{_sign(key, body)}"


def shown_at(
    token: Optional[str],
    *,
    workspace_id,
    form_id,
    provider: str,
    provider_name: str,
    enabled_at: dt.datetime,
    now: Optional[dt.datetime] = None,
) -> Optional[dt.datetime]:
    """When the notice was shown, if ``token`` is a valid, unexpired token for
    this form under its current setting; otherwise None (never an error: a
    submission without a valid token is stored, just never analysed)."""
    key = _key()
    if key is None or not token or not isinstance(token, str):
        return None
    if len(token) > MAX_TOKEN_LENGTH:
        return None
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _VERSION:
        return None
    body = f"{parts[0]}.{parts[1]}"
    try:
        if not hmac.compare_digest(_sign(key, body), parts[2]):
            return None
        claims = json.loads(_unb64(parts[1]))
    except (ValueError, TypeError):
        return None
    if not isinstance(claims, dict):
        return None
    expected = _claims(workspace_id, form_id, provider, provider_name, enabled_at)
    if any(claims.get(name) != value for name, value in expected.items()):
        return None
    issued_ms = claims.get("i")
    if not isinstance(issued_ms, int) or isinstance(issued_ms, bool):
        return None
    issued = dt.datetime.fromtimestamp(issued_ms / 1000, tz=dt.timezone.utc)
    current = _utc(now or dt.datetime.now(dt.timezone.utc))
    if issued > current + CLOCK_SKEW or current - issued > TOKEN_TTL:
        return None
    # shown under this setting, never before it was turned on
    if issued_ms < expected["e"]:
        return None
    return issued


def _notice_in_force(association) -> Optional[tuple]:
    """(provider, provider name, enabled at) while respondents of this form
    are shown the notice: the form is collected here (an imported form's
    respondents answer elsewhere) and allows AI insights."""
    form_settings = getattr(association, "settings", None)
    if form_settings is None or getattr(form_settings, "provider", None) != "self":
        return None
    if not getattr(form_settings, "ai_insights_enabled", None):
        return None
    provider = getattr(form_settings, "ai_insights_provider", None)
    name = getattr(form_settings, "ai_insights_provider_name", None)
    enabled_at = getattr(form_settings, "ai_insights_enabled_at", None)
    if not provider or not name or not enabled_at:
        return None
    return provider, name, enabled_at


def token_for_form(workspace_id, association) -> Optional[str]:
    """The token a respondent's form page gets with the form, or None while
    the page shows no AI notice."""
    in_force = _notice_in_force(association)
    if association is None or in_force is None:
        return None
    provider, name, enabled_at = in_force
    return issue_token(
        workspace_id=workspace_id,
        form_id=association.form_id,
        provider=provider,
        provider_name=name,
        enabled_at=enabled_at,
    )


def stamp_response(response, token: Optional[str], workspace_id, association) -> bool:
    """Record on ``response`` that the notice was shown, when ``token`` proves
    it for this form's current setting. Whatever the client sent for these
    fields is dropped first: only the server sets them."""
    response.ai_notice_shown_at = None
    response.ai_notice_provider_name = None
    in_force = _notice_in_force(association)
    if association is None or in_force is None:
        return False
    provider, name, enabled_at = in_force
    shown = shown_at(
        token,
        workspace_id=workspace_id,
        form_id=association.form_id,
        provider=provider,
        provider_name=name,
        enabled_at=enabled_at,
    )
    if shown is None:
        return False
    response.ai_notice_shown_at = shown
    response.ai_notice_provider_name = name
    return True
