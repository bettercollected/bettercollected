"""Save and continue later: a respondent's draft of a form.

Rules this module keeps (the design is in backend/AGENTS.md "Drafts"):

- A draft is not a response. It lives in its own table, is never read by the
  responses repositories and so appears in no list, export, count, response
  limit, action, webhook or registration until the form is submitted; the
  submit is the normal one, and deletes the draft afterwards.
- Answers, hidden-field values and the page position are one payload,
  encrypted with the response keyset, bound to the workspace and form and to
  the draft's id (``crypto_service`` context), so a ciphertext cannot be
  moved to another draft or read as a response.
- Every read and write names workspace, form and the draft in the query; a
  draft of another account, workspace or form is simply not found.
- A signed-in respondent's draft is theirs by account. An anonymous one is
  reached by the magic link's token (mailed, expiring, a keyed hash at rest,
  constant-time compare) or by the edit key the browser that created it holds.
  The respondent's address is used to send one mail and is never stored (only
  a keyed hash of it, to cap drafts per address). No answer is ever in a mail
  or a log: logs name counts and our codes.
- Failures that could tell an attacker something answer the same: an unknown,
  expired, mismatched or malformed token is one 404, whatever the reason.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from http import HTTPStatus
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from common.clock import utcnow
from common.ids import RecordId
from common.models.user import User
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from sqlalchemy.exc import IntegrityError

from backend.app.exceptions import HTTPException
from backend.app.schemas.form_draft import FormDraftDocument
from backend.app.services import form_availability
from backend.app.services.form_drafts import limits, tokens
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.rate_limiter import FixedWindowRateLimiter, Verdict
from backend.app.services.retention import retention_date
from backend.app.utils.client_ip import rate_limit_key
from backend.config import settings as app_settings

DRAFTS_OFF = "drafts_off"
DRAFT_NOT_FOUND = "draft_not_found"
SIGN_IN_REQUIRED = "sign_in_required"
DRAFT_TOO_LARGE = "draft_too_large"
LINK_NOT_SENT = "link_not_sent"
NOTIFY_PATH = "/notifications/draft-link"
NOTIFY_TIMEOUT_SECONDS = 10
MAX_DEPTH = 16
MAX_HIDDEN_FIELDS = 100
MAX_POSITION_PAGES = 500


def _error(status: int, code: str, message: str, **headers: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        content={"code": code, "message": message},
        headers=headers or None,
    )


def not_found() -> HTTPException:
    """The one answer for a draft that cannot be opened, whatever the
    reason (unknown, expired, another form's, a wrong or malformed token)."""
    return _error(HTTPStatus.NOT_FOUND, DRAFT_NOT_FOUND, "There is no such draft.")


def _too_many(verdict: Verdict) -> HTTPException:
    return _error(
        HTTPStatus.TOO_MANY_REQUESTS,
        "rate_limited",
        f"Too many attempts. Retry after {verdict.retry_after} seconds.",
        **{"Retry-After": str(verdict.retry_after)},
    )


def _depth(value: Any, cap: int = MAX_DEPTH) -> int:
    """How deeply JSON ``value`` nests (iterative: no recursion limit to hit)."""
    deepest, pending = 0, [(value, 1)]
    while pending:
        item, level = pending.pop()
        if isinstance(item, dict):
            children = item.values()
        elif isinstance(item, list):
            children = item
        else:
            continue
        deepest = max(deepest, level)
        if deepest > cap:
            return deepest
        pending.extend((child, level + 1) for child in children)
    return deepest


class _Camel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class DraftPosition(_Camel):
    """Where the respondent was: the page's id and the pages visited, so Back
    retraces jumps. Ids, not indexes: a changed form still finds its pages."""

    page_id: Optional[str] = Field(None, max_length=100)
    history: List[str] = Field(default_factory=list, max_length=MAX_POSITION_PAGES)

    @field_validator("history")
    @classmethod
    def _short_ids(cls, ids: List[str]) -> List[str]:
        if any(not isinstance(i, str) or len(i) > 100 for i in ids):
            raise ValueError("Page ids are short texts.")
        return ids


class DraftContent(_Camel):
    """What a draft holds: the same answers the form submits (files are not
    saved), the hidden-field values and the position."""

    answers: Dict[str, Any] = Field(default_factory=dict)
    hidden_fields: Dict[str, str] = Field(default_factory=dict)
    position: Optional[DraftPosition] = None

    @field_validator("hidden_fields")
    @classmethod
    def _few_hidden(cls, values: Dict[str, str]) -> Dict[str, str]:
        if len(values) > MAX_HIDDEN_FIELDS or any(
            len(k) > 200 or len(v) > 2000 for k, v in values.items()
        ):
            raise ValueError("Too many or too long hidden-field values.")
        return values


class SaveDraftBody(DraftContent):
    # the browser's edit key (anonymous respondents); signed-in ones need none
    edit_key: Optional[str] = None
    form_version: Optional[int] = Field(None, ge=0, le=1_000_000)


class LinkRequestBody(SaveDraftBody):
    email: str = Field(..., min_length=3, max_length=254)
    # the respondent's page language, for the mail (en or nl); else the form's
    locale: Optional[str] = Field(None, max_length=35)


class OpenDraftBody(_Camel):
    token: str


class DiscardBody(_Camel):
    token: Optional[str] = None
    edit_key: Optional[str] = None


class SavedDto(_Camel):
    saved_at: dt.datetime
    expires_at: dt.datetime


class LinkSentDto(SavedDto):
    # the key this browser saves with from now on; never the link's token
    edit_key: str


class DraftDto(DraftContent):
    saved_at: dt.datetime
    expires_at: dt.datetime
    form_version: Optional[int] = None
    # the form's published version now, and whether it is not the one saved
    current_version: Optional[int] = None
    form_changed: bool = False
    # the key to save with from now on (anonymous respondents who opened a link)
    edit_key: Optional[str] = None


class DraftUnavailableDto(_Camel):
    """The form takes no responses now (closed, not open yet, full): no
    answers are handed back, the draft stays until it expires."""

    unavailable: str
    expires_at: dt.datetime


def _address(value: str) -> str:
    """A normalised address, or 422. Checked with the same validator the
    other address inputs use; no look-up, no verification beyond the mail."""
    from pydantic import TypeAdapter, EmailStr, ValidationError

    text = (value or "").strip()
    try:
        return str(TypeAdapter(EmailStr).validate_python(text)).casefold()
    except ValidationError:
        raise _error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_email",
            "Enter an email address.",
        )


class FormDraftService:
    def __init__(
        self,
        draft_repo,
        workspace_form_repo,
        form_repo,
        workspace_repo,
        form_response_service,
        crypto,
        rate_limiter: FixedWindowRateLimiter,
        http_client,
        secret: str,
        clock=utcnow,
    ):
        self._drafts = draft_repo
        self._workspace_forms = workspace_form_repo
        self._forms = form_repo
        self._workspaces = workspace_repo
        self._responses = form_response_service
        self._crypto = crypto
        self._limiter = rate_limiter
        self._http = http_client
        self._keys = tokens.DraftKeys(secret)
        self._clock = clock

    # ------------------------------------------------------------ the form

    async def _form(self, workspace_id: RecordId, form_id: str, user: Optional[User]):
        """The workspace's link to the form, when this respondent may answer it
        and it lets them save drafts; 404 otherwise. Also the published
        version (a form never published takes no drafts)."""
        visible = await self._workspace_forms.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=True,
            user=user,
            form_id_or_slug=str(form_id),
        )
        link = (
            await self._workspace_forms.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=str(form_id)
            )
            if visible
            else None
        )
        if link is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found")
        if not limits.saving_enabled(link.settings):
            raise _error(
                HTTPStatus.NOT_FOUND,
                DRAFTS_OFF,
                "This form does not keep drafts.",
            )
        version = await self._forms.get_latest_version_of_form(
            form_id=RecordId(link.form_id)
        )
        if version is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found")
        return link, version

    async def _ensure_takes_responses(
        self, link, workspace_id: RecordId, received_at=None
    ) -> None:
        """A closed, not yet open or full form takes no drafts either: the
        same refusals as a submission (409)."""
        form_availability.ensure_accepting_responses(
            link.settings, received_at=received_at
        )
        if form_availability.response_limit(link.settings) is not None:
            form_availability.ensure_not_full(
                link.settings,
                await self._responses.count_for_form(workspace_id, str(link.form_id)),
            )

    async def _unavailable(self, link, workspace_id: RecordId) -> Optional[str]:
        reason = form_availability.date_unavailability(link.settings)
        if reason or form_availability.response_limit(link.settings) is None:
            return reason
        count = await self._responses.count_for_form(workspace_id, str(link.form_id))
        return (
            form_availability.UNAVAILABLE_FULL
            if form_availability.is_full(link.settings, count)
            else None
        )

    def _expiry(self, link, created_at: dt.datetime, now: dt.datetime) -> dt.datetime:
        """Retention days from this save, never past 90 days from the first
        save, never past a fixed retention date of the form."""
        expires = min(
            now + dt.timedelta(days=limits.draft_days(link.settings)),
            created_at + limits.ABSOLUTE_LIFETIME,
        )
        settings = link.settings
        kind = getattr(
            getattr(settings, "response_expiration_type", None), "value", None
        ) or getattr(settings, "response_expiration_type", None)
        if kind == "date":
            day = retention_date(getattr(settings, "response_expiration", None))
            if day is not None:
                end = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
                expires = min(expires, end)
        if expires <= now + dt.timedelta(minutes=1):
            # the form's own retention ends now: it could not keep a draft
            raise _error(
                HTTPStatus.CONFLICT,
                DRAFTS_OFF,
                "This form cannot keep a draft any longer.",
            )
        return expires

    # ------------------------------------------------------- the payload

    def _seal(self, workspace_id, form_id, draft_id, content: DraftContent) -> str:
        data = json.dumps(
            {
                "answers": content.answers,
                "hiddenFields": content.hidden_fields,
                "position": (
                    content.position.model_dump(by_alias=True)
                    if content.position
                    else None
                ),
            },
            separators=(",", ":"),
        )
        if (
            len(data.encode()) > limits.MAX_PAYLOAD_BYTES
            or _depth(content.answers) > MAX_DEPTH
        ):
            raise _error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                DRAFT_TOO_LARGE,
                "This draft is too large to save.",
            )
        import base64

        return base64.b64encode(
            self._crypto.encrypt(
                workspace_id=str(workspace_id),
                form_id=str(form_id),
                data=data,
                context=_context(draft_id),
            )
        ).decode("ascii")

    def _unseal(self, draft: FormDraftDocument) -> DraftContent:
        import base64

        try:
            plain = self._crypto.decrypt(
                workspace_id=str(draft.workspace_id),
                form_id=str(draft.form_id),
                data=base64.b64decode(draft.payload),
                context=_context(draft.id),
            )
            if isinstance(plain, (bytes, bytearray)):
                plain = plain.decode()
            stored = json.loads(plain)
            return DraftContent.model_validate(stored)
        except Exception:  # noqa: BLE001 - unreadable: treated as no draft
            logger.warning(
                "form draft {} could not be read (workspace {}, form {})",
                draft.id,
                draft.workspace_id,
                draft.form_id,
            )
            raise not_found()

    # --------------------------------------------------------- rate limits

    async def _limit(
        self, spec, client: Optional[str], extra: str = "", amount: int = 1
    ) -> Verdict:
        scope, limit, window = spec
        verdict = await self._limiter.hit(
            scope, f"{rate_limit_key(client)}{extra}", limit, window, amount=amount
        )
        if not verdict.allowed:
            logger.info("Draft request refused: too many requests ({})", scope)
            raise _too_many(verdict)
        return verdict

    async def _limit_key(self, spec, key: str) -> None:
        scope, limit, window = spec
        verdict = await self._limiter.hit(scope, key, limit, window)
        if not verdict.allowed:
            logger.info("Draft request refused: too many requests ({})", scope)
            raise _too_many(verdict)

    # ---------------------------------------------------------- the saves

    async def save(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: Optional[User],
        body: SaveDraftBody,
        client: Optional[str],
        received_at: Optional[dt.datetime] = None,
    ) -> SavedDto:
        """Save the draft of the signed-in respondent, or update the
        anonymous one the browser's edit key names. An anonymous respondent
        without a draft has none to update (404): they start with a link."""
        link, version = await self._form(workspace_id, form_id, user)
        await self._limit(limits.SAVES_PER_CLIENT, client)
        await self._ensure_takes_responses(link, workspace_id, received_at)
        now = self._clock()
        real_form_id = str(link.form_id)
        if user is not None:
            return await self._save_for_owner(
                workspace_id, real_form_id, link, version, user, body, now
            )
        draft = await self._by_secret(
            workspace_id, real_form_id, body.edit_key, tokens.EDIT_KEY
        )
        if draft is None:
            raise not_found()
        draft.payload = self._seal(workspace_id, real_form_id, draft.id, body)
        draft.form_version = body.form_version or version.version
        draft.expires_at = self._expiry(link, draft.created_at, now)
        saved = await self._drafts.save(draft)
        return SavedDto(saved_at=saved.updated_at, expires_at=saved.expires_at)

    async def _save_for_owner(
        self, workspace_id, form_id, link, version, user, body, now
    ) -> SavedDto:
        owner = str(user.id)
        for attempt in (1, 2):
            draft = await self._drafts.for_owner(workspace_id, form_id, owner)
            if draft is None:
                draft = FormDraftDocument(
                    workspace_id=workspace_id,
                    form_id=form_id,
                    owner_id=owner,
                    payload="",
                    expires_at=now,
                ).ensure_id()
            draft.payload = self._seal(workspace_id, form_id, draft.id, body)
            draft.form_version = body.form_version or version.version
            draft.expires_at = self._expiry(link, draft.created_at, now)
            try:
                saved = await self._drafts.save(draft)
            except IntegrityError:
                # two first saves at once: the other one won, update that draft
                if attempt == 2:
                    raise
                continue
            return SavedDto(saved_at=saved.updated_at, expires_at=saved.expires_at)
        raise AssertionError("unreachable")

    async def request_link(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: Optional[User],
        body: LinkRequestBody,
        client: Optional[str],
        received_at: Optional[dt.datetime] = None,
    ) -> LinkSentDto:
        """Create (or, with the browser's edit key, update) an anonymous draft
        and mail its link to the address the respondent entered. The mail
        holds the form, the organisation and the link; never an answer."""
        link, version = await self._form(workspace_id, form_id, user)
        real_form_id = str(link.form_id)
        if link.settings.require_verified_identity:
            # an emailed link would be a way round the sign-in the form asks for
            raise _error(
                HTTPStatus.FORBIDDEN,
                SIGN_IN_REQUIRED,
                "Sign in to save a draft of this form.",
            )
        if user is not None:
            raise _error(
                HTTPStatus.CONFLICT,
                "use_account",
                "Signed-in respondents save to their account.",
            )
        address = _address(body.email)
        email_key = self._keys.address_key(real_form_id, address)
        # every request counts, wherever it is refused later: per client, per
        # address on this form, and per form (one form cannot mail the world)
        await self._limit(limits.LINK_PER_CLIENT, client)
        await self._limit_key(limits.LINK_PER_ADDRESS, email_key)
        await self._limit_key(limits.LINK_PER_FORM, f"{workspace_id}:{real_form_id}")
        await self._ensure_takes_responses(link, workspace_id, received_at)
        now = self._clock()
        draft = await self._by_secret(
            workspace_id, real_form_id, body.edit_key, tokens.EDIT_KEY
        )
        if draft is None:
            draft = FormDraftDocument(
                workspace_id=workspace_id,
                form_id=real_form_id,
                email_key=email_key,
                payload="",
                expires_at=now,
            ).ensure_id()
            created = True
        else:
            created = False
        draft.payload = self._seal(workspace_id, real_form_id, draft.id, body)
        draft.form_version = body.form_version or version.version
        draft.expires_at = self._expiry(link, draft.created_at, now)
        # a new link replaces the old one; the edit key is the browser's
        secret = tokens.new_secret()
        edit_secret = tokens.new_secret()
        draft.token_hash = self._keys.hash_secret(tokens.TOKEN, draft.id, secret)
        draft.token_expires_at = min(now + limits.LINK_LIFETIME, draft.expires_at)
        draft.edit_key_hash = self._keys.hash_secret(
            tokens.EDIT_KEY, draft.id, edit_secret
        )
        draft.email_key = email_key
        if created:
            saved = await self._drafts.create_for_address(
                draft, limits.MAX_DRAFTS_PER_ADDRESS, now
            )
            if saved is None:
                logger.info("Draft refused: address at its draft limit")
                raise _too_many(Verdict(False, 0, limits.HOUR))
        else:
            saved = await self._drafts.save(draft)
        await self._mail_link(
            link, workspace_id, address, tokens.compose(saved.id, secret), body.locale
        )
        return LinkSentDto(
            saved_at=saved.updated_at,
            expires_at=saved.expires_at,
            edit_key=tokens.compose(saved.id, edit_secret),
        )

    async def _mail_link(
        self, link, workspace_id: RecordId, address: str, token: str, locale
    ) -> None:
        """Ask the auth service to mail the link. The address is passed on and
        not kept; a failure is logged without it and tells the respondent the
        link did not go out (they can try again)."""
        try:
            workspace = await self._workspaces.get_workspace_by_id(workspace_id)
            form = await self._forms.get_form_document_by_id(str(link.form_id))
            language = getattr(getattr(form, "settings", None), "language", None)
            base = (app_settings.api_settings.CLIENT_URL or "").rstrip("/")
            url = (
                f"{base}/{quote(workspace.workspace_name, safe='')}/forms/"
                f"{quote(str(link.form_id), safe='')}#resume={token}"
            )
            chosen = locale or language
            response = await self._http.post(
                app_settings.auth_settings.BASE_URL + NOTIFY_PATH,
                json={
                    "recipient": address,
                    "form_title": (form.title if form else None) or "a form",
                    "workspace_title": workspace.title or None,
                    "link": url,
                    "days": limits.LINK_LIFETIME.days,
                    **({"locale": chosen} if chosen else {}),
                },
                headers=auth_service_headers(),
                timeout=NOTIFY_TIMEOUT_SECONDS,
            )
            del response
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "Draft link not sent: workspace={} form={} ({})",
                workspace_id,
                link.form_id,
                type(error).__name__,
            )
            raise _error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                LINK_NOT_SENT,
                "The link could not be sent. Try again in a moment.",
            )

    # ----------------------------------------------------------- the reads

    async def _by_secret(
        self,
        workspace_id: RecordId,
        form_id: str,
        value: Optional[str],
        purpose: str,
    ) -> Optional[FormDraftDocument]:
        """The draft a token or edit key opens: for this workspace and form,
        live, with the right secret of the right purpose, else None."""
        parts = tokens.split(value)
        if parts is None:
            return None
        draft_id, secret = parts
        draft = await self._drafts.get(workspace_id, form_id, draft_id)
        # compared even for a missing draft: the time does not tell them apart
        stored = None
        if draft is not None:
            stored = (
                draft.token_hash if purpose == tokens.TOKEN else draft.edit_key_hash
            )
        right = self._keys.matches(purpose, draft_id, secret, stored)
        now = self._clock()
        if draft is None or not right or draft.expires_at <= now:
            return None
        if (
            purpose == tokens.TOKEN
            and draft.token_expires_at is not None
            and draft.token_expires_at <= now
        ):
            return None
        return draft

    async def open_with_token(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: Optional[User],
        body: OpenDraftBody,
        client: Optional[str],
    ):
        """Open the draft a magic link names. Anything wrong with the link is
        one 404 (``draft_not_found``); failed attempts are limited per client.
        Hands out a new edit key: the browser can save from here."""
        await self._limit(limits.OPENS_PER_CLIENT, client)
        scope, limit, window = limits.OPEN_MISSES_PER_CLIENT
        key = rate_limit_key(client)
        misses = await self._limiter.hit(scope, key, limit, window, amount=0)
        if misses.count >= limit:
            raise _too_many(misses)
        try:
            link, version = await self._form(workspace_id, form_id, user)
            draft = await self._by_secret(
                workspace_id, str(link.form_id), body.token, tokens.TOKEN
            )
            if draft is None:
                raise not_found()
        except HTTPException as refused:
            if refused.status_code == HTTPStatus.NOT_FOUND:
                await self._limiter.hit(scope, key, limit, window)
                # a link to a form that turned drafts off is just a dead link
                raise not_found()
            raise
        edit_secret = tokens.new_secret()
        draft.edit_key_hash = self._keys.hash_secret(
            tokens.EDIT_KEY, draft.id, edit_secret
        )
        await self._drafts.save(draft)
        return await self._view(
            link, version, workspace_id, draft, tokens.compose(draft.id, edit_secret)
        )

    async def mine(
        self, workspace_id: RecordId, form_id: str, user: User, client: Optional[str]
    ):
        """The signed-in respondent's own draft of the form; 404 without one."""
        link, version = await self._form(workspace_id, form_id, user)
        await self._limit(limits.OPENS_PER_CLIENT, client)
        draft = await self._drafts.for_owner(
            workspace_id, str(link.form_id), str(user.id)
        )
        if draft is None or draft.expires_at <= self._clock():
            raise not_found()
        return await self._view(link, version, workspace_id, draft, None)

    async def _view(self, link, version, workspace_id, draft, edit_key):
        reason = await self._unavailable(link, workspace_id)
        if reason:
            return DraftUnavailableDto(unavailable=reason, expires_at=draft.expires_at)
        content = self._unseal(draft)
        return DraftDto(
            answers=content.answers,
            hidden_fields=content.hidden_fields,
            position=content.position,
            saved_at=draft.updated_at,
            expires_at=draft.expires_at,
            form_version=draft.form_version,
            current_version=version.version,
            form_changed=draft.form_version != version.version,
            edit_key=edit_key,
        )

    # ----------------------------------------------------------- erasure

    async def discard(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: Optional[User],
        body: DiscardBody,
        client: Optional[str],
    ) -> None:
        """Delete the respondent's own draft: the signed-in one by account, an
        anonymous one by its edit key or its link's token. Allowed whether or
        not the form still takes drafts (erasure is never refused)."""
        await self._limit(limits.OPENS_PER_CLIENT, client)
        await self._discard(workspace_id, form_id, user, body)

    async def _discard(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: Optional[User],
        body: DiscardBody,
    ) -> None:
        link = await self._workspace_forms.get_workspace_form_in_workspace(
            workspace_id=workspace_id, query=str(form_id)
        )
        if link is None:
            raise not_found()
        real_form_id = str(link.form_id)
        deleted = 0
        if user is not None:
            deleted += await self._drafts.delete_for_owner(
                workspace_id, real_form_id, str(user.id)
            )
        for secret, purpose in (
            (body.edit_key, tokens.EDIT_KEY),
            (body.token, tokens.TOKEN),
        ):
            draft = await self._by_secret(workspace_id, real_form_id, secret, purpose)
            if draft is not None:
                deleted += await self._drafts.delete(
                    workspace_id, real_form_id, draft.id
                )
        if not deleted:
            raise not_found()

    async def delete_after_submit(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: Optional[User],
        edit_key: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        """The submission was stored: its draft goes. Never fails the submit
        (a draft left behind expires on its own and the purge removes it)."""
        try:
            await self._discard(
                workspace_id, form_id, user, DiscardBody(token=token, edit_key=edit_key)
            )
        except HTTPException as refused:
            if refused.status_code != HTTPStatus.NOT_FOUND:
                logger.warning(
                    "Draft not deleted after submit: workspace={} form={}",
                    workspace_id,
                    form_id,
                )
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "Draft not deleted after submit: workspace={} form={} ({})",
                workspace_id,
                form_id,
                type(error).__name__,
            )

    async def delete_for_form(self, workspace_id: RecordId, form_id: str) -> None:
        await self._drafts.delete_for_form(workspace_id, form_id)

    async def delete_for_forms(self, form_ids: List[str]) -> None:
        await self._drafts.delete_by_form_ids(form_ids)

    async def delete_for_workspaces(self, workspace_ids: List[RecordId]) -> None:
        await self._drafts.delete_by_workspace_ids(workspace_ids)

    async def delete_for_account(self, user_id: str) -> int:
        """Every draft of a deleted account, in every workspace."""
        return await self._drafts.delete_by_owner(user_id)

    # ------------------------------------------------------------- purge

    async def purge(self) -> Dict[str, int]:
        """The daily purge: expired drafts, and the drafts of forms that no
        longer keep them (the setting is off, or the form is gone from the
        workspace). Counts only."""
        expired = await self._drafts.delete_expired(self._clock())
        orphaned = 0
        for workspace_id, form_id in await self._drafts.form_keys():
            link = await self._workspace_forms.find_workspace_form(
                workspace_id, form_id
            )
            if link is None or not limits.saving_enabled(link.settings):
                orphaned += await self._drafts.delete_for_form(workspace_id, form_id)
            await asyncio.sleep(0)
        return {"expired": expired, "unwanted": orphaned}


def _context(draft_id) -> bytes:
    return f"draft|{draft_id}".encode()
