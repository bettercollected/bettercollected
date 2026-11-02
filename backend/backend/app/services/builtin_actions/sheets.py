"""The Google Sheets action, run by the backend (``docs/executor-isolation.md``
describes the executor this replaces for it).

A form's Google Sheets action appends one row per submission to a spreadsheet,
keeps the header row in step with the form's questions and adds one tab per
repeating group that is laid out as rows. This module does what the actions
executor did for it, in the backend's jobs worker, on the ``integrations`` queue:

- the log row of a run (the shared action log, type ``sheets``) is the job's only
  argument, so no answer, address or credential sits in the queue;
- the credential and the spreadsheet id are read and opened inside the job
  (the layers of the action, the workspace and the form, the form's last);
- every call goes to Google's own hosts, which are constants here (never a
  stored address; the credential's ``token_uri`` is ignored), through the
  backend's pinned client (``registration.client``: https, public addresses, no
  redirects, bounded time); the spreadsheet id is checked before it is part of a
  path;
- the access token is refreshed here and the refreshed credential is sealed
  again with the backend's own key, never handed anywhere;
- permanent answers (the sheet is gone, access was withdrawn) end the run, a
  server error or a rate limit is tried again (3 attempts: after 5 s, then 25 s).

The answers' texts come from ``qa`` (the port of the executor's extraction), so
the sheet's columns and cells are what they were. A part of a run that is done
(the row, then each group tab) is recorded on the log row, so a retry does not
append it twice; a crash between an append and that record can still append a
row twice (as it could before).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode, urlsplit

from common.clock import utcnow
from common.ids import RecordId
from loguru import logger
from procrastinate import BaseRetryStrategy
from procrastinate.retry import RetryDecision

from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.schemas.webhook import ActionLogDocument, ActionType, LogStatus
from backend.app.services.builtin_actions import qa
from backend.app.services.internal_fields import strip_internal_fields
from backend.app.services.registration import client

SHEETS_ACTION = "integrate_google_sheets"
SHEETS_HOST = "sheets.googleapis.com"
TOKEN_HOST = "oauth2.googleapis.com"
SHEETS_URL = f"https://{SHEETS_HOST}/v4/spreadsheets"
TOKEN_URL = f"https://{TOKEN_HOST}/token"
ALLOWED_HOSTS = (SHEETS_HOST, TOKEN_HOST)
SPREADSHEET_ID = re.compile(r"^[A-Za-z0-9_-]{20,100}$")
# the format of the stored credential's expiry (the Google libraries' own)
EXPIRY_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
TIMEOUTS = {"connect": 5.0, "read": 15.0, "write": 15.0, "pool": 5.0}
TOTAL_TIMEOUT_S = 20.0
MAX_REPLY_BYTES = 1024 * 1024
MAX_ATTEMPTS = 3
RETRY_WAITS = (5, 25)
REDEFER_AFTER = dt.timedelta(minutes=2)
STUCK_AFTER = dt.timedelta(minutes=30)
SWEEP_BATCH = 200
PARAMETER_SHEET_ID = "Google Sheet Id"
SECRET_CREDENTIALS = "Credentials"

_OPEN_STATES = (LogStatus.PENDING, LogStatus.RETRYING)

HEADER_FORMAT = {
    "textFormat": {"bold": True, "underline": True},
    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
}
ROW_FORMAT = {
    "textFormat": {"bold": False, "underline": False},
    "backgroundColor": {"red": 0.8, "green": 0.9, "blue": 1},
}


def runs_in_backend(entry: Any) -> bool:
    """Whether the form's action entry is run by this module (the move of the
    built-in Google Sheets action marked it ``migrated_to`` ``sheets``)."""
    marker = getattr(entry, "migrated_to", None)
    return isinstance(marker, dict) and marker.get("kind") == "sheets"


class SheetsRetryStrategy(BaseRetryStrategy):
    """3 attempts in all: a second 5 seconds after the first failed, a third 25
    seconds after the second; a longer ``Retry-After`` of Google wins."""

    def get_retry_decision(self, *, exception, job):
        if job.attempts + 1 >= MAX_ATTEMPTS:
            return None
        wait = RETRY_WAITS[min(job.attempts, len(RETRY_WAITS) - 1)]
        after = getattr(exception, "retry_after", None) or 0
        return RetryDecision(retry_in={"seconds": max(wait, after)})


def retry_wait(attempt: int) -> int:
    """Seconds to wait after attempt number ``attempt`` (1-based) failed."""
    return RETRY_WAITS[min(max(attempt, 1), len(RETRY_WAITS)) - 1]


class SheetsRetry(Exception):
    """Raised by the job so procrastinate retries it (never carries content)."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__("retry")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Outcome:
    status: str
    retry: bool = False
    retry_after: Optional[int] = None


def _failed(code: str, *, permanent: bool, http_status: Optional[int] = None):
    return client.SendFailed(code, permanent=permanent, http_status=http_status)


# ------------------------------------------------------------------ Google


class GoogleApi:
    """The few calls the action makes, to Google's two hosts."""

    def __init__(self, request: Callable[..., Awaitable[client.Reply]] = None):
        # tests replace it with a fake Google; the default is the pinned client
        self._request = request or client.request

    async def _call(
        self,
        method: str,
        url: str,
        *,
        token: Optional[str] = None,
        body: Optional[bytes] = None,
        query: Optional[List[Tuple[str, str]]] = None,
        content_type: bytes = b"application/json",
        on_status: Optional[Dict[int, Tuple[str, bool]]] = None,
    ) -> Any:
        """One call; the parsed JSON of the reply. ``on_status`` maps an HTTP
        status to ``(code, permanent)``."""
        if urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise _failed("config_invalid", permanent=True)
        headers = []
        if token:
            headers.append((b"Authorization", b"Bearer " + token.encode("ascii")))
        try:
            reply = await self._request(
                client.Target(base_url=url),
                method,
                body=body,
                query=query,
                extra_headers=headers,
                keep_reply=True,
                max_reply=MAX_REPLY_BYTES,
                timeouts=TIMEOUTS,
                total_timeout=TOTAL_TIMEOUT_S,
                content_type=content_type,
            )
        except client.SendFailed as failed:
            mapped = (on_status or {}).get(failed.http_status or 0)
            if mapped:
                raise client.SendFailed(
                    mapped[0],
                    permanent=mapped[1],
                    http_status=failed.http_status,
                    retry_after=failed.retry_after,
                )
            raise
        if reply.truncated or not reply.body:
            return {}
        try:
            parsed = json.loads(reply.body)
        except ValueError:
            raise _failed("bad_reply", permanent=False)
        return parsed if isinstance(parsed, dict) else {}

    async def refresh(self, credential: Dict[str, Any]) -> Dict[str, Any]:
        """A new access token for the credential's refresh token, always from
        Google's token host (``token_uri`` of the credential is not read)."""
        form = urlencode(
            {
                "client_id": credential.get("client_id") or "",
                "client_secret": credential.get("client_secret") or "",
                "refresh_token": credential.get("refresh_token") or "",
                "grant_type": "refresh_token",
            }
        ).encode()
        reply = await self._call(
            "POST",
            TOKEN_URL,
            body=form,
            content_type=b"application/x-www-form-urlencoded",
            # a refused refresh token (revoked, expired) or client
            on_status={400: ("oauth_token_missing", True), 401: ("oauth_token_missing", True)},
        )
        token, lifetime = reply.get("access_token"), reply.get("expires_in")
        if not isinstance(token, str) or not token or not isinstance(lifetime, (int, float)):
            raise _failed("oauth_token_missing", permanent=True)
        return {"token": token, "expires_in": lifetime}

    # the spreadsheet's own calls: 404 is a sheet that is gone, 401 a token
    # Google no longer accepts, 403 access that was withdrawn
    _SHEET_STATUS = {
        401: ("oauth_token_missing", True),
        403: ("sheet_access_denied", True),
        404: ("sheet_missing", True),
    }

    async def _sheet(self, method, path, token, *, body=None, query=None):
        return await self._call(
            method,
            f"{SHEETS_URL}/{path}",
            token=token,
            body=None if body is None else json.dumps(body).encode(),
            query=query,
            on_status=self._SHEET_STATUS,
        )

    @staticmethod
    def _range(text: str) -> str:
        return quote(text, safe="")

    async def first_row(self, sheet_id: str, token: str) -> List[Any]:
        got = await self._sheet(
            "GET", f"{sheet_id}/values/{self._range('A1:1')}", token
        )
        rows = got.get("values") or [[]]
        return list(rows[0]) if rows and isinstance(rows[0], list) else []

    async def write_row(self, sheet_id: str, token: str, range_: str, values: List[Any]):
        """Replace the cells of ``range_`` (a header row). ``RAW``: the question
        titles are the creator's, so no title is ever read as a formula or a
        date, and what is written is what the form says."""
        await self._sheet(
            "POST",
            f"{sheet_id}/values:batchUpdate",
            token,
            body={
                "valueInputOption": "RAW",
                "data": [{"range": range_, "values": [values]}],
            },
        )

    async def format_cells(
        self, sheet_id: str, token: str, row: int, columns: int, cell: Dict[str, Any], fields: str
    ) -> None:
        """Colour a row. Cosmetic: a failure here never fails the run (the row
        is already there, and a retry would append it again)."""
        try:
            await self._sheet(
                "POST",
                f"{sheet_id}:batchUpdate",
                token,
                body={
                    "requests": [
                        {
                            "repeatCell": {
                                "range": {
                                    "sheetId": 0,
                                    "startRowIndex": row,
                                    "endRowIndex": row + 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": columns,
                                },
                                "cell": {"userEnteredFormat": cell},
                                "fields": fields,
                            }
                        }
                    ]
                },
            )
        except client.SendFailed as failed:
            logger.info("sheets formatting skipped: code={}", failed.code)

    async def append(self, sheet_id: str, token: str, range_: str, rows: List[List[Any]]) -> Dict[str, Any]:
        return await self._sheet(
            "POST",
            f"{sheet_id}/values/{self._range(range_)}:append",
            token,
            body={"values": rows},
            query=[("valueInputOption", "USER_ENTERED"), ("insertDataOption", "INSERT_ROWS")],
        )

    async def tab_titles(self, sheet_id: str, token: str) -> set:
        got = await self._sheet(
            "GET", sheet_id, token, query=[("fields", "sheets.properties.title")]
        )
        return {
            s["properties"]["title"]
            for s in got.get("sheets", [])
            if isinstance(s, dict) and isinstance(s.get("properties"), dict)
        }

    async def add_tab(self, sheet_id: str, token: str, title: str) -> None:
        await self._sheet(
            "POST",
            f"{sheet_id}:batchUpdate",
            token,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        )


# ------------------------------------------------------------------ the run


def _layer(*layers) -> Dict[str, str]:
    """The values of the action, the workspace and the form, the later one
    winning name by name; a value that is empty is not one."""
    merged: Dict[str, str] = {}
    for items in layers:
        for item in items or []:
            name, value = getattr(item, "name", None), getattr(item, "value", None)
            if name is not None and value not in (None, ""):
                merged[name] = value
    return merged


def _credential_expired(credential: Dict[str, Any], now: dt.datetime) -> bool:
    try:
        expiry = dt.datetime.strptime(credential.get("expiry") or "", EXPIRY_FORMAT)
    except ValueError:
        return True
    return expiry < now


class SheetsRunService:
    def __init__(
        self,
        *,
        log_repo,
        form_repo,
        action_repo,
        workspace_repo,
        form_response_service,
        form_actions_service,
        crypto,
        sheets_reconsent=None,
        api: Optional[GoogleApi] = None,
        defer: Optional[Callable[[str], Awaitable[None]]] = None,
        clock: Callable[[], dt.datetime] = utcnow,
    ):
        self._logs = log_repo
        self._forms = form_repo
        self._actions = action_repo
        self._workspaces = workspace_repo
        self._responses = form_response_service
        self._form_actions = form_actions_service
        self._crypto = crypto
        self._reconsent = sheets_reconsent
        self._api = api or GoogleApi()
        self._defer = defer or _defer_job
        self._clock = clock

    # ------------------------------------------------------- on submission

    async def queue_for_submission(
        self, workspace_id: RecordId, form_id: str, response_id: str, action_id: str
    ) -> Optional[str]:
        """Called after a response is stored, for an action the backend runs:
        one log row (the idempotency key is the action and the response) and a
        job by its id. Calls nothing external and never raises. Returns the log
        id, or None when there was one already."""
        try:
            log = await self._logs.create_if_absent(
                ActionLogDocument(
                    workspace_id=workspace_id,
                    form_id=str(form_id),
                    action_type=ActionType.SHEETS,
                    action_id=str(action_id),
                    response_id=str(response_id),
                )
            )
            if log is None:
                return None
            await self._queue(log)
            return str(log.id)
        except Exception as error:  # noqa: BLE001 - never fail a submission
            logger.error(
                "sheets run not queued: workspace={} form={} response={} ({})",
                workspace_id,
                form_id,
                response_id,
                type(error).__name__,
            )
            return None

    async def _queue(self, log: ActionLogDocument) -> bool:
        try:
            await self._defer(str(log.id))
            return True
        except Exception as error:  # noqa: BLE001
            logger.error(
                "could not queue sheets run {} ({})", log.id, type(error).__name__
            )
            return False

    # ------------------------------------------------------------- the job

    async def run_delivery(self, log_id: str) -> Outcome:
        """One attempt of one run (the ``run_sheets_append`` job). The attempt
        count is the log row's own."""
        log = await self._logs.claim(log_id, _OPEN_STATES, now=self._clock())
        if log is None:
            return Outcome("skipped")
        final = log.attempts >= MAX_ATTEMPTS
        try:
            return await self._attempt(log)
        except client.SendFailed as failed:
            return await self._settle(log, failed.code, failed.http_status, final, failed.permanent, failed.retry_after)
        except Exception as error:  # noqa: BLE001 - record, then retry or give up
            logger.error(
                "sheets attempt crashed: run={} ({})", log.id, type(error).__name__
            )
            return await self._settle(log, "internal_error", None, final, False, None)

    async def _settle(self, log, code, http_status, final, permanent, retry_after) -> Outcome:
        log.last_error_code = code
        log.last_http_status = http_status
        if permanent or final:
            log.status = LogStatus.FAILED
            log.next_attempt_at = None
            log.finished_at = self._clock()
            await self._logs.save_existing(log)
            logger.warning(
                "sheets run failed: run={} code={} http={} attempts={}",
                log.id, code, http_status, log.attempts,
            )
            return Outcome("failed")
        wait = max(retry_wait(log.attempts), retry_after or 0)
        log.status = LogStatus.RETRYING
        log.next_attempt_at = self._clock() + dt.timedelta(seconds=wait)
        await self._logs.save_existing(log)
        logger.info(
            "sheets run will retry: run={} code={} http={} attempt={} in={}s",
            log.id, code, http_status, log.attempts, wait,
        )
        return Outcome("retrying", retry=True, retry_after=retry_after)

    async def _cancel(self, log: ActionLogDocument, code: str) -> Outcome:
        log.status = LogStatus.CANCELLED
        log.last_error_code = code
        log.next_attempt_at = None
        log.finished_at = self._clock()
        await self._logs.save_existing(log)
        logger.info("sheets run cancelled: run={} code={}", log.id, code)
        return Outcome("cancelled")

    async def _entry(self, form_document, action_id: str):
        for entry in (form_document.actions or {}).get("on_submit") or []:
            if str(entry.id) == str(action_id):
                return entry
        return None

    async def _attempt(self, log: ActionLogDocument) -> Outcome:
        form_document = await self._forms.get_form_document_by_id(str(log.form_id))
        entry = await self._entry(form_document, log.action_id) if form_document else None
        if entry is None or not entry.enabled or not runs_in_backend(entry):
            return await self._cancel(log, "disabled")
        response = await self._responses.workspace_response(
            log.workspace_id, str(log.response_id)
        )
        if response is None or str(response.form_id) != str(log.form_id):
            # erasure wins over a late run: the submission is gone, so is the row
            await self._logs.delete_by_response_id(
                log.workspace_id, log.form_id, str(log.response_id)
            )
            logger.info("sheets run dropped, response gone: run={}", log.id)
            return Outcome("gone")
        action = await self._actions.get_action_by_id(RecordId(str(log.action_id)))
        if action is None or getattr(action, "name", None) != SHEETS_ACTION:
            return await self._cancel(log, "disabled")
        if self._reconsent is not None and await self._reconsent.hold_back_run(
            form_document, action, log.workspace_id
        ):
            return await self._cancel(log, "reconsent_needed")
        workspace = await self._workspace_copy(log.workspace_id, action.id)
        if workspace is None:
            return await self._cancel(log, "disabled")
        parameters = _layer(
            action.parameters,
            (workspace.parameters or {}).get(str(action.id)),
            (form_document.parameters or {}).get(str(action.id)),
        )
        secrets = _layer(
            action.secrets,
            (workspace.secrets or {}).get(str(action.id)),
            (form_document.secrets or {}).get(str(action.id)),
        )
        sheet_id = parameters.get(PARAMETER_SHEET_ID) or ""
        if not SPREADSHEET_ID.match(sheet_id):
            raise _failed("sheet_id_invalid", permanent=True)
        credential = self._open_credential(secrets.get(SECRET_CREDENTIALS))
        # the answers: in memory, for this attempt
        decrypted = self._responses.decrypt_form_response(
            workspace_id=log.workspace_id, response=response
        )
        form_view = self._form_view(await self._form_for(response))
        response_view = {
            "response_id": str(response.response_id),
            "answers": decrypted.answers if isinstance(decrypted.answers, dict) else {},
        }
        data = qa.get_questions_and_answers(form_view, response_view, fixed_columns=True)
        tables = qa.get_group_tables(form_view, response_view)
        del decrypted, response_view
        token = await self._access_token(credential, log)
        if log.steps_done < 1:
            await self._append_row(sheet_id, token, data)
            log.steps_done = 1
            await self._logs.save_existing(log)
        await self._append_tables(sheet_id, token, tables, log)
        del data, tables
        log.status = LogStatus.DELIVERED
        log.finished_at = self._clock()
        log.last_error_code = None
        log.last_http_status = None
        log.next_attempt_at = None
        await self._logs.save_existing(log)
        logger.info("sheets run delivered: run={} attempts={}", log.id, log.attempts)
        return Outcome("delivered")

    # ------------------------------------------------------------ the parts

    async def _workspace_copy(self, workspace_id, action_id):
        from backend.app.exceptions import HTTPException as AppHTTPException
        from backend.app.models.workspace import WorkspaceRequestWithActionDto

        try:
            raw = await self._workspaces.get_workspace_with_action_by_id(
                workspace_id=workspace_id, action_id=action_id
            )
        except AppHTTPException:
            return None
        return WorkspaceRequestWithActionDto(**raw) if raw is not None else None

    async def _form_for(self, response):
        version = getattr(response, "form_version", None)
        form = (
            await self._forms.get_form_by_by_version(response.form_id, version)
            if version
            else None
        )
        return (
            form
            or await self._forms.get_latest_version_of_form(response.form_id)
            or await self._forms.get_form_document_by_id(str(response.form_id))
        )

    @staticmethod
    def _form_view(form: Any) -> Dict[str, Any]:
        copy = form.model_copy(deep=True) if hasattr(form, "model_copy") else form
        stripped = strip_internal_fields(copy)
        return stripped.model_dump(mode="json") if hasattr(stripped, "model_dump") else dict(stripped or {})

    def _open_credential(self, sealed: Optional[str]) -> Dict[str, Any]:
        if not sealed:
            raise _failed("oauth_token_missing", permanent=True)
        try:
            credential = json.loads(self._crypto.decrypt(sealed))
        except Exception:  # noqa: BLE001 - a value no key opens, or not JSON
            raise _failed("secret_unreadable", permanent=True)
        if not isinstance(credential, dict):
            raise _failed("secret_unreadable", permanent=True)
        return credential

    async def _access_token(self, credential: Dict[str, Any], log: ActionLogDocument) -> str:
        """The credential's access token, refreshed (and the credential stored
        again, sealed here) when it has expired."""
        token = credential.get("token")
        if token and not _credential_expired(credential, self._clock().replace(tzinfo=None)):
            return token
        if not credential.get("refresh_token"):
            raise _failed("oauth_token_missing", permanent=True)
        fresh = await self._api.refresh(credential)
        credential["token"] = fresh["token"]
        credential["expiry"] = (
            self._clock().replace(tzinfo=None) + dt.timedelta(seconds=fresh["expires_in"])
        ).strftime(EXPIRY_FORMAT)
        try:
            await self._form_actions.update_run_secret(
                RecordId(str(log.form_id)),
                RecordId(str(log.action_id)),
                FormActionsDto(
                    name=SECRET_CREDENTIALS, value=json.dumps(credential), type="secrets"
                ),
            )
        except Exception as error:  # noqa: BLE001 - the run goes on with the token
            logger.warning(
                "sheets credential not stored: run={} ({})", log.id, type(error).__name__
            )
        return fresh["token"]

    async def _append_row(self, sheet_id: str, token: str, data: List[Dict[str, Any]]) -> None:
        # a title is written as it is (RAW: never a formula); USER_ENTERED runs
        # cells that start with = + - @ as formulas, so an answer never goes
        # in unguarded
        titles = [entry["title"] for entry in data]
        answers = [qa.formula_safe(entry["answer"]) for entry in data]
        existing = await self._api.first_row(sheet_id, token)
        changed = False
        for index, title in enumerate(titles):
            if index < len(existing):
                if existing[index] != title:
                    existing[index] = title
                    changed = True
            else:
                existing.append(title)
                changed = True
        if changed:
            await self._api.write_row(
                sheet_id, token, f"A1:{qa.column_letter(len(existing))}1", existing
            )
            await self._api.format_cells(
                sheet_id, token, 0, len(titles), HEADER_FORMAT,
                "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor",
            )
        appended = await self._api.append(sheet_id, token, "A2", [answers])
        row = self._appended_row(appended)
        if row is not None:
            await self._api.format_cells(
                sheet_id, token, row, len(answers), ROW_FORMAT,
                "userEnteredFormat.backgroundColor",
            )

    @staticmethod
    def _appended_row(reply: Dict[str, Any]) -> Optional[int]:
        """The 0-based index of the row Google appended, from its range."""
        updates = reply.get("updates") if isinstance(reply, dict) else None
        text = updates.get("updatedRange") if isinstance(updates, dict) else None
        match = re.search(r"!\$?[A-Z]+\$?(\d+)", text) if isinstance(text, str) else None
        return int(match.group(1)) - 1 if match else None

    async def _append_tables(self, sheet_id, token, tables, log) -> None:
        """Rows-layout repeating groups: a tab each, a header row, a row per item."""
        if not tables:
            return
        existing = await self._api.tab_titles(sheet_id, token)
        for position, table in enumerate(tables):
            step = position + 2  # step 1 is the row of answers
            if log.steps_done >= step:
                continue
            title = table.get("sheet_title") or qa.sheet_title_for(table["title"])
            if not _path_safe_title(title):
                raise _failed("sheet_title_unsupported", permanent=True)
            if title not in existing:
                await self._api.add_tab(sheet_id, token, title)
                existing.add(title)
            await self._api.write_row(
                sheet_id,
                token,
                f"'{title}'!A1:{qa.column_letter(len(table['headers']))}1",
                list(table["headers"]),
            )
            if table["rows"]:
                await self._api.append(
                    sheet_id,
                    token,
                    f"'{title}'!A2",
                    [[qa.formula_safe(v) for v in row] for row in table["rows"]],
                )
            log.steps_done = step
            await self._logs.save_existing(log)

    # ---------------------------------------------------------------- sweeps

    async def redefer_pending(self) -> Dict[str, int]:
        """Queue again the runs whose job never got queued and rescue ones whose
        worker died mid-attempt."""
        now = self._clock()
        queued = 0
        for log in await self._logs.list_pending_before(
            now - REDEFER_AFTER, SWEEP_BATCH, ActionType.SHEETS
        ):
            queued += 1 if await self._queue(log) else 0
        rescued = failed = 0
        for status, before in (
            (LogStatus.IN_PROGRESS, now - STUCK_AFTER),
            (LogStatus.RETRYING, now - STUCK_AFTER),
        ):
            for log in await self._logs.list_stuck(status, before, SWEEP_BATCH, ActionType.SHEETS):
                if log.attempts >= MAX_ATTEMPTS:
                    # the last attempt's worker died: there is no attempt left, so
                    # the run ends visibly instead of going round again
                    log.status = LogStatus.FAILED
                    log.last_error_code = "worker_lost"
                    log.next_attempt_at = None
                    log.finished_at = now
                    if await self._logs.save_existing(log):
                        failed += 1
                    continue
                log.status = LogStatus.PENDING
                if await self._logs.save_existing(log):
                    rescued += 1 if await self._queue(log) else 0
        return {"queued": queued, "rescued": rescued, "failed": failed}


def _path_safe_title(title: str) -> bool:
    """A tab name goes into a request path: the pinned client refuses ``..``
    (also encoded) in a path, so a name with it cannot be addressed."""
    return ".." not in title


async def _defer_job(log_id: str) -> None:
    """Queue ``run_sheets_append`` for a log row: the id is the only argument."""
    from procrastinate.exceptions import AlreadyEnqueued

    from backend.jobs import tasks

    try:
        await tasks.run_sheets_append.configure(
            queueing_lock=f"run_sheets_append:{log_id}"
        ).defer_async(log_id=log_id)
    except AlreadyEnqueued:
        pass
