"""Proof that the settings marked hot (reload class H) in the settings
inventory are read at call time: each test changes the value on the loaded
settings object after the consumer was built and checks the consumer's next
call uses it. A key that is read at import or when the container is built can
not pass these tests, and must stay R (see ``TODO_LIVE`` in
``common/settings/inventory.py``).

``common/tests/settings/test_inventory.py`` requires every H key to be named
here, so the keys appear as strings in the parametrisation.
"""

from types import SimpleNamespace

import pytest

from backend.app.exceptions import HTTPException
from backend.app.public_api import auth as public_auth
from backend.app.services import unsplash_route
from backend.app.services.ai import usage as ai_usage
from backend.app.services.ai.usage import AIUsageGuard
from backend.app.services.flow_event_service import FlowEventService
from backend.app.services.form_spec.editor_ops import EditorOpsService
from backend.app.services.image_service import ImageService
from backend.app.services.rate_limiter import Verdict
from backend.config import settings


class RecordingLimiter:
    """Records every ``hit``; answers with ``verdicts`` in order (then the
    last one again)."""

    def __init__(self, *verdicts: Verdict):
        self.calls = []
        self._verdicts = list(verdicts) or [Verdict(True, 1, 1)]

    async def hit(self, scope, client, limit, window_seconds, amount=1):
        self.calls.append((scope, client, limit, window_seconds))
        index = min(len(self.calls), len(self._verdicts)) - 1
        return self._verdicts[index]


ALLOW = Verdict(True, 1, 1)
DENY = Verdict(False, 99, 7)


def _set(monkeypatch, target, field, value):
    assert hasattr(target, field), field
    monkeypatch.setattr(target, field, value)


# ---------------------------------------------------------------- AI


async def _admit(limiter, **kw):
    await AIUsageGuard(limiter).admit("workspace-1", kw.get("user", "user-1"))


@pytest.mark.parametrize(
    "key, field, slot, position",
    [
        ("AI_RATE_LIMIT_PER_USER", "RATE_LIMIT_PER_USER", 0, 2),
        ("AI_RATE_LIMIT_WINDOW_SECONDS", "RATE_LIMIT_WINDOW_SECONDS", 0, 3),
        ("AI_RATE_LIMIT_PER_WORKSPACE", "RATE_LIMIT_PER_WORKSPACE", 1, 2),
    ],
)
async def test_ai_request_limits_are_read_per_call(monkeypatch, key, field, slot, position):
    limiter = RecordingLimiter()
    await _admit(limiter)
    before = limiter.calls[slot][position]
    new = before + 1234
    _set(monkeypatch, settings.ai, field, new)
    limiter = RecordingLimiter()
    await _admit(limiter)
    assert limiter.calls[slot][position] == new, key


async def test_ai_fix_limit_and_window_are_read_per_call(monkeypatch):
    # AI_RATE_LIMIT_FIX_PER_USER and AI_RATE_LIMIT_WINDOW_SECONDS
    _set(monkeypatch, settings.ai, "RATE_LIMIT_FIX_PER_USER", 4321)
    _set(monkeypatch, settings.ai, "RATE_LIMIT_WINDOW_SECONDS", 777)
    limiter = RecordingLimiter()
    await AIUsageGuard(limiter).admit_fix("workspace-1", "user-1")
    assert limiter.calls[0][2:] == (4321, 777)
    _set(monkeypatch, settings.ai, "RATE_LIMIT_FIX_PER_USER", 0)
    limiter = RecordingLimiter()
    await AIUsageGuard(limiter).admit_fix("workspace-1", "user-1")
    assert limiter.calls == []


async def test_ai_daily_request_budget_is_read_per_call(monkeypatch):
    # AI_DAILY_REQUEST_BUDGET: the workspace has made 5 requests today
    used = Verdict(True, 5, 60)
    _set(monkeypatch, settings.ai, "DAILY_REQUEST_BUDGET", 0)
    await _admit(RecordingLimiter(used))
    _set(monkeypatch, settings.ai, "DAILY_REQUEST_BUDGET", 3)
    with pytest.raises(Exception) as caught:
        await _admit(RecordingLimiter(used))
    assert getattr(caught.value, "status_code", None) == 429
    _set(monkeypatch, settings.ai, "DAILY_REQUEST_BUDGET", 50)
    await _admit(RecordingLimiter(used))


async def test_ai_daily_token_budget_is_read_per_call(monkeypatch):
    # AI_DAILY_TOKEN_BUDGET: 100 tokens spent today
    spent = Verdict(True, 100, 60)
    _set(monkeypatch, settings.ai, "DAILY_REQUEST_BUDGET", 0)
    _set(monkeypatch, settings.ai, "DAILY_TOKEN_BUDGET", 0)
    await _admit(RecordingLimiter(spent))
    _set(monkeypatch, settings.ai, "DAILY_TOKEN_BUDGET", 50)
    with pytest.raises(Exception) as caught:
        await _admit(RecordingLimiter(spent))
    assert getattr(caught.value, "status_code", None) == 429
    _set(monkeypatch, settings.ai, "DAILY_TOKEN_BUDGET", 5000)
    await _admit(RecordingLimiter(spent))


# ------------------------------------------------------------ public API


@pytest.mark.parametrize(
    "key, field, slot, position",
    [
        ("API_PUBLIC_API_REQUESTS_PER_WINDOW", "PUBLIC_API_REQUESTS_PER_WINDOW", 0, 2),
        ("API_PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", "PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", 1, 2),
        ("API_PUBLIC_API_WINDOW_SECONDS", "PUBLIC_API_WINDOW_SECONDS", 0, 3),
        ("API_PUBLIC_API_WINDOW_SECONDS", "PUBLIC_API_WINDOW_SECONDS", 1, 3),
    ],
)
async def test_public_api_limits_are_read_per_call(monkeypatch, key, field, slot, position):
    limiter = RecordingLimiter()
    monkeypatch.setattr(
        public_auth, "_c", lambda: SimpleNamespace(rate_limiter=lambda: limiter)
    )
    api_key = SimpleNamespace(id="key-1", workspace_id="ws-1")
    new = 4242 + slot
    _set(monkeypatch, settings.api_settings, field, new)
    await public_auth._rate_limit(api_key)
    assert limiter.calls[slot][position] == new, key


# ----------------------------------------------------------- flow events


@pytest.mark.parametrize(
    "key, field, position",
    [
        ("API_FLOW_EVENTS_PER_WINDOW", "FLOW_EVENTS_PER_WINDOW", 2),
        ("API_FLOW_EVENTS_WINDOW_SECONDS", "FLOW_EVENTS_WINDOW_SECONDS", 3),
    ],
)
async def test_flow_event_limits_are_read_per_call(monkeypatch, key, field, position):
    limiter = RecordingLimiter(DENY)
    service = FlowEventService(None, None, None, limiter)

    async def servable(workspace_id, form_ref, fresh=False):
        return SimpleNamespace(form_id="form-1")

    monkeypatch.setattr(service, "_servable_form", servable)
    for new in (4001, 4002):
        _set(monkeypatch, settings.api_settings, field, new)
        with pytest.raises(HTTPException):
            await service.record("ws", "form-1", SimpleNamespace(), None)
        assert limiter.calls[-1][position] == new, key


# --------------------------------------------------------------- images


def _image_service(limiter):
    async def allow(*args, **kwargs):
        return None

    authorization = SimpleNamespace(authorize=allow)
    return ImageService(SimpleNamespace(), limiter, authorization)


@pytest.mark.parametrize(
    "key, field, position",
    [
        ("API_IMAGE_PROXY_PER_WINDOW", "IMAGE_PROXY_PER_WINDOW", 2),
        ("API_IMAGE_PROXY_WINDOW_SECONDS", "IMAGE_PROXY_WINDOW_SECONDS", 3),
    ],
)
async def test_image_proxy_limits_are_read_per_call(monkeypatch, key, field, position):
    monkeypatch.setattr(unsplash_route, "is_photo_path", lambda path: True)
    monkeypatch.setattr(unsplash_route, "clean_params", lambda query: {})
    limiter = RecordingLimiter(DENY)
    service = _image_service(limiter)
    for new in (5001, 5002):
        _set(monkeypatch, settings.api_settings, field, new)
        with pytest.raises(HTTPException):
            await service.serve_unsplash("photo-1", [], "203.0.113.9")
        assert limiter.calls[-1][position] == new, key


@pytest.mark.parametrize(
    "key, field, call, position",
    [
        ("API_IMAGE_PROXY_FETCHES_PER_WINDOW", "IMAGE_PROXY_FETCHES_PER_WINDOW", 0, 2),
        ("API_IMAGE_PROXY_WINDOW_SECONDS", "IMAGE_PROXY_WINDOW_SECONDS", 0, 3),
        ("API_IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW", "IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW", 1, 2),
        ("API_IMAGE_PROXY_WINDOW_SECONDS", "IMAGE_PROXY_WINDOW_SECONDS", 1, 3),
    ],
)
async def test_image_fetch_limits_are_read_per_call(monkeypatch, key, field, call, position):
    limiter = RecordingLimiter(ALLOW, DENY)
    service = _image_service(limiter)
    new = 6000 + call
    _set(monkeypatch, settings.api_settings, field, new)
    with pytest.raises(HTTPException):
        await service._fetch_unsplash("photo-1", {}, "object-key", "client-1")
    assert limiter.calls[call][position] == new, key


@pytest.mark.parametrize(
    "key, field, position",
    [
        ("API_IMAGE_IMPORTS_PER_WINDOW", "IMAGE_IMPORTS_PER_WINDOW", 2),
        ("API_IMAGE_IMPORTS_WINDOW_SECONDS", "IMAGE_IMPORTS_WINDOW_SECONDS", 3),
    ],
)
async def test_image_import_limits_are_read_per_call(monkeypatch, key, field, position):
    limiter = RecordingLimiter(DENY)
    service = _image_service(limiter)
    user = SimpleNamespace(id="user-1")
    for new in (7001, 7002):
        _set(monkeypatch, settings.api_settings, field, new)
        with pytest.raises(HTTPException):
            await service.import_image("ws", "https://images.example.org/a.png", user)
        assert limiter.calls[-1][position] == new, key


# ------------------------------------------------------------ editor ops


def _editor_service(limiter, authorization=None):
    return EditorOpsService(authorization, None, None, None, rate_limiter=limiter)


@pytest.mark.parametrize(
    "key, field, position",
    [
        ("API_EDITOR_OPS_PER_WINDOW", "EDITOR_OPS_PER_WINDOW", 2),
        ("API_EDITOR_OPS_WINDOW_SECONDS", "EDITOR_OPS_WINDOW_SECONDS", 3),
    ],
)
async def test_editor_ops_limits_are_read_per_call(monkeypatch, key, field, position):
    limiter = RecordingLimiter(ALLOW)
    service = _editor_service(limiter)
    for new in (8001, 8002):
        _set(monkeypatch, settings.api_settings, field, new)
        await service._rate_limit(SimpleNamespace(id="user-1"))
        assert limiter.calls[-1][position] == new, key


async def test_editor_ops_save_flag_is_read_per_call(monkeypatch):
    # API_EDITOR_OPS_SAVE_ENABLED: off means no permission lookup at all
    asked = []

    async def has_permission(*args):
        asked.append(args)
        return False

    service = _editor_service(None, SimpleNamespace(has_permission=has_permission))
    user = SimpleNamespace(id="user-1")
    _set(monkeypatch, settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", False)
    assert await service.etag_for_editor(user, "ws", "form-1") is None
    assert asked == []
    _set(monkeypatch, settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", True)
    assert await service.etag_for_editor(user, "ws", "form-1") is None
    assert len(asked) == 1
    _set(monkeypatch, settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", False)
    await service.etag_for_editor(user, "ws", "form-1")
    assert len(asked) == 1


def test_the_ai_usage_module_keeps_its_scopes():
    # the AI tests above identify calls by position: fail loudly if that changes
    assert ai_usage.USER_SCOPE != ai_usage.WORKSPACE_SCOPE
