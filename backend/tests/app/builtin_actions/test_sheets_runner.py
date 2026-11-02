"""The Google Sheets action run by the backend (``builtin_actions/sheets.py``):
what is queued, what is appended, how the credential is used and kept, what is
retried and what ends a run, and what never leaves the backend. Google is a fake
that keeps a spreadsheet; one test goes through the real pinned client."""

import datetime as dt
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from common.models.standard_form import ActionState, ParameterValue, Trigger
from loguru import logger

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import FormActionType, FormIntegrationType
from backend.app.schemas.webhook import ActionType, LogStatus
from backend.app.services.builtin_actions import sheets
from backend.app.services.registration import client
from backend.jobs import tasks
from tests.app.controllers.data import testUser
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.registration.helpers import ANSWERS, FIELDS, publish, submit

pytestmark = pytest.mark.asyncio

SHEET = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdE"
SECRET_TOKEN = "ya29.SECRET-ACCESS-TOKEN"
PERSONAL = ["Ada Example", "ada@example.test", "Synthetic story."]


class FakeGoogle:
    """The two Google hosts, for the calls the runner makes. Keeps one
    spreadsheet: tabs of a header row and rows; records every call."""

    def __init__(self):
        self.tabs = {"Sheet1": {"header": None, "rows": []}}
        self.calls = []
        self.fail = {}  # a label of a call -> the SendFailed it raises
        self.token_reply = {"access_token": "fresh-access-token", "expires_in": 3600}
        self.formats = []

    def _tab_of(self, range_):
        range_ = unquote(range_)
        if "!" in range_:
            name, _, cell = range_.rpartition("!")
            return name.strip("'"), cell
        return "Sheet1", range_

    async def request(
        self, target, method, *, body=None, query=None, extra_headers=(), keep_reply=False,
        max_reply=None, user_agent=None, timeouts=None, total_timeout=None,
        content_type=b"application/json",
    ):
        url = target.base_url
        parts = urlsplit(url)
        headers = {k.decode().lower(): v.decode() for k, v in extra_headers}
        self.calls.append(
            SimpleNamespace(method=method, url=url, host=parts.hostname, body=body,
                            query=dict(query or []), headers=headers, content_type=content_type)
        )
        label = f"{method} {parts.path.rsplit('/', 1)[-1]}"
        for key, failure in self.fail.items():
            if key in label or key in url:
                raise failure
        if parts.hostname == "oauth2.googleapis.com":
            return self._json(self.token_reply)
        assert parts.hostname == "sheets.googleapis.com", url
        path = parts.path.removeprefix("/v4/spreadsheets/")
        sheet_id, _, rest = path.partition("/")
        if ":" in sheet_id:  # {id}:batchUpdate
            sheet_id, _, op = sheet_id.partition(":")
            return self._batch_update(json.loads(body))
        if rest.startswith("values:batchUpdate"):
            data = json.loads(body)["data"][0]
            tab, _cell = self._tab_of(data["range"])
            self.tabs[tab]["header"] = data["values"][0]
            return self._json({})
        if rest.startswith("values/") and rest.endswith(":append"):
            tab, _cell = self._tab_of(rest[len("values/"):-len(":append")])
            rows = json.loads(body)["values"]
            self.tabs[tab]["rows"].extend(rows)
            last = 1 + len(self.tabs[tab]["rows"])
            return self._json({"updates": {"updatedRange": f"{tab}!A{last}:Z{last}"}})
        if rest.startswith("values/"):
            header = self.tabs["Sheet1"]["header"]
            return self._json({"values": [header]} if header else {})
        # the spreadsheet itself: its tabs
        return self._json({"sheets": [{"properties": {"title": t}} for t in self.tabs]})

    def _batch_update(self, body):
        for item in body["requests"]:
            if "addSheet" in item:
                self.tabs[item["addSheet"]["properties"]["title"]] = {"header": None, "rows": []}
            else:
                self.formats.append(item["repeatCell"])
        return self._json({})

    @staticmethod
    def _json(value):
        return client.Reply(200, json.dumps(value).encode())

    def appends(self):
        return [c for c in self.calls if c.url.endswith(":append")]


def failed(code, status, permanent):
    return client.SendFailed(code, permanent=permanent, http_status=status)


def credential(expired=False, token=SECRET_TOKEN):
    expiry = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(
        hours=-1 if expired else 1
    )
    return {
        "token": token,
        "refresh_token": "refresh-token-value",
        "token_uri": "https://evil.example/steal",
        "client_id": "client-id-value",
        "client_secret": "client-secret-value",
        "scopes": "https://www.googleapis.com/auth/drive.file",
        "expiry": expiry.strftime(sheets.EXPIRY_FORMAT),
    }


@pytest.fixture()
def lines():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(handler)


@pytest.fixture()
def google():
    fake = FakeGoogle()
    service = container.sheets_run_service()
    original = service._api
    service._api = sheets.GoogleApi(fake.request)
    yield fake
    service._api = original


async def attach(workspace, form, *, marked=True, sheet_id=SHEET, cred=None, enabled=True):
    """The Sheets action on the form: its workspace copy, the sheet id and the
    credential on the form, and (``marked``) the backend's mark on the entry."""
    action = await container.action_repository().create_global_action(
        ActionDto(
            name=FormIntegrationType.GOOGLE_SHEET.value,
            action_code="",
            type=FormActionType.EXTERNAL.value,
        ),
        testUser,
    )
    await container.action_repository().create_action_in_workspace_from_action(
        workspace_id=workspace.id, action_id=action.id
    )
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(form.form_id)
    entry = ActionState(id=action.id, enabled=enabled)
    if marked:
        entry.migrated_to = {"kind": "sheets", "id": str(action.id)}
    document.actions = {Trigger.on_submit: [entry]}
    document.parameters = {str(action.id): [ParameterValue(name="Google Sheet Id", value=sheet_id)]}
    sealed = container.crypto().encrypt(json.dumps(cred if cred is not None else credential()))
    document.secrets = {str(action.id): [ParameterValue(name="Credentials", value=sealed)]}
    await repo.save_form(document)
    return action


async def setup_run(workspace, memory_jobs, **kwargs):
    form = await publish(workspace)
    action = await attach(workspace, form, **kwargs)
    return SimpleNamespace(workspace=workspace, form=form, action=action, jobs=memory_jobs)


async def runs_of(form):
    rows = await container.action_log_repo().many()
    return [r for r in rows if r.form_id == form.form_id and r.action_type is ActionType.SHEETS]


async def run(log):
    return await container.sheets_run_service().run_delivery(str(log.id))


async def run_one(setup, **kwargs):
    response = await submit(setup.workspace, setup.form, **kwargs)
    (log,) = [r for r in await runs_of(setup.form) if r.response_id == response.response_id]
    return response, log


# ------------------------------------------------------------------ queueing


async def test_a_run_the_backend_took_over_is_queued_by_id_on_the_integrations_queue(
    workspace, memory_jobs, google, lines
):
    setup = await setup_run(workspace, memory_jobs)
    response, log = await run_one(setup)
    assert log.status is LogStatus.PENDING and log.attempts == 0
    jobs = list(memory_jobs.jobs.values())
    assert len(jobs) == 1  # nothing for the executor
    (job,) = jobs
    assert job["task_name"] == "run_sheets_append" and job["queue_name"] == "integrations"
    assert dict(job["args"]) == {"log_id": str(log.id)}
    dumped = json.dumps(job, default=str)
    for text in PERSONAL + [SHEET, SECRET_TOKEN, "refresh-token-value"]:
        assert text not in dumped
    assert google.calls == []  # nothing external on the request path


async def test_an_action_that_is_not_taken_over_still_goes_to_the_executor(
    workspace, memory_jobs, google
):
    setup = await setup_run(workspace, memory_jobs, marked=False)
    response = await submit(setup.workspace, setup.form)
    assert await runs_of(setup.form) == []
    assert [j["queue_name"] for j in memory_jobs.jobs.values()] == ["actions"]


async def test_a_repeat_queue_call_is_a_no_op(workspace, memory_jobs, google):
    setup = await setup_run(workspace, memory_jobs)
    response, log = await run_one(setup)
    again = await container.sheets_run_service().queue_for_submission(
        workspace.id, setup.form.form_id, response.response_id, setup.action.id
    )
    assert again is None and len(memory_jobs.jobs) == 1


# ----------------------------------------------------------------- the rows


async def test_the_run_writes_the_header_and_appends_the_row_of_answers(
    workspace, memory_jobs, google, lines
):
    setup = await setup_run(workspace, memory_jobs)
    response, log = await run_one(setup)
    assert (await run(log)).status == "delivered"
    tab = google.tabs["Sheet1"]
    titles = [e["title"] for e in sheets.qa.get_questions_and_answers(
        sheets.SheetsRunService._form_view(
            await container.form_repo().get_latest_version_of_form(setup.form.form_id)
        ),
        {"response_id": response.response_id, "answers": ANSWERS},
        fixed_columns=True,
    )]
    assert tab["header"] == titles and titles[:2] == ["Full name", "Your story"]
    (row,) = tab["rows"]
    assert row[0] == "Ada Example" and row[3] == 36 and row[4] == "Yes"
    # every call carried the token as a bearer, to Google's hosts only
    assert {c.host for c in google.calls} == {"sheets.googleapis.com"}
    assert all(c.headers["authorization"] == f"Bearer {SECRET_TOKEN}" for c in google.calls)
    # the header and the row are coloured, and the first sheet is the one
    assert [f["range"]["startRowIndex"] for f in google.formats] == [0, 1]
    done = await container.action_log_repo().get(log.id)
    assert done.status is LogStatus.DELIVERED and done.attempts == 1 and done.steps_done >= 1
    stored = json.dumps(done.model_dump(mode="json"))
    for text in PERSONAL + [SHEET, SECRET_TOKEN]:
        assert text not in stored and not any(text in line for line in lines), text
    assert (await run(log)).status == "skipped" and len(tab["rows"]) == 1


async def test_a_second_submission_adds_a_row_and_a_new_question_adds_a_column(
    workspace, memory_jobs, google
):
    setup = await setup_run(workspace, memory_jobs)
    for _ in range(2):
        _response, log = await run_one(setup)
        assert (await run(log)).status == "delivered"
    tab = google.tabs["Sheet1"]
    assert len(tab["rows"]) == 2
    writes = [c for c in google.calls if c.url.endswith("values:batchUpdate")]
    assert len(writes) == 1  # the header was written once, then it matched
    google.tabs["Sheet1"]["header"] = tab["header"][:-3] + ["An old title"]
    _response, log = await run_one(setup)
    assert (await run(log)).status == "delivered"
    assert len([c for c in google.calls if c.url.endswith("values:batchUpdate")]) == 2
    # the stale title is put right: the header is the form's questions again
    assert "An old title" not in google.tabs["Sheet1"]["header"]
    assert len(google.tabs["Sheet1"]["rows"]) == 3


async def test_a_text_that_starts_like_a_formula_is_kept_as_text(workspace, memory_jobs, google):
    setup = await setup_run(workspace, memory_jobs)
    answers = {**ANSWERS, "name": {"type": "text", "text": '=HYPERLINK("http://x")'},
               "story": {"type": "text", "text": "+1 -2"}}
    _response, log = await run_one(setup, answers=answers)
    assert (await run(log)).status == "delivered"
    (row,) = google.tabs["Sheet1"]["rows"]
    assert row[0] == "'=HYPERLINK(\"http://x\")" and row[1] == "'+1 -2"


async def test_a_large_repeating_group_gets_its_own_tab_and_a_retry_does_not_repeat_the_row(
    workspace, memory_jobs, google
):
    fields = [dict(f) for f in FIELDS]
    group = next(f for f in fields if f["id"] == "people")
    group["properties"] = {**group["properties"], "repeat": {"minItems": 0, "maxItems": 10, "itemLabel": "Person"}}
    form = await publish(workspace, fields=fields)
    action = await attach(workspace, form)
    setup = SimpleNamespace(workspace=workspace, form=form, action=action)
    _response, log = await run_one(setup)
    google.fail["People"] = failed("http_5xx", 503, False)
    outcome = await run(log)
    assert outcome.status == "retrying" and outcome.retry
    assert len(google.tabs["Sheet1"]["rows"]) == 1
    google.fail.clear()
    again = await container.action_log_repo().get(log.id)
    assert again.status is LogStatus.RETRYING and again.steps_done == 1
    assert (await run(again)).status == "delivered"
    assert len(google.tabs["Sheet1"]["rows"]) == 1  # not appended twice
    tab = google.tabs["People"]
    assert tab["header"][:3] == ["Response ID", "Person", "Person name"]
    assert [r[1:3] for r in tab["rows"]] == [[1, "Bo"], [2, "Cy"]]


# -------------------------------------------------------------- credentials


async def test_an_expired_token_is_refreshed_at_googles_own_host_and_stored_sealed(
    workspace, memory_jobs, google, lines
):
    setup = await setup_run(workspace, memory_jobs, cred=credential(expired=True))
    _response, log = await run_one(setup)
    assert (await run(log)).status == "delivered"
    (refresh,) = [c for c in google.calls if c.host == "oauth2.googleapis.com"]
    assert refresh.url == "https://oauth2.googleapis.com/token"  # not the credential's token_uri
    assert refresh.content_type == b"application/x-www-form-urlencoded"
    form = parse_qs(refresh.body.decode())
    assert form["grant_type"] == ["refresh_token"] and form["client_id"] == ["client-id-value"]
    assert all(c.headers["authorization"] == "Bearer fresh-access-token"
               for c in google.calls if c.host == "sheets.googleapis.com")
    stored = (await container.form_repo().get_form_document_by_id(setup.form.form_id)).secrets
    (secret,) = stored[str(setup.action.id)]
    assert secret.name == "Credentials" and "fresh-access-token" not in secret.value  # sealed
    kept = json.loads(container.crypto().decrypt(secret.value))
    assert kept["token"] == "fresh-access-token" and kept["refresh_token"] == "refresh-token-value"
    for text in ("fresh-access-token", "refresh-token-value", "client-secret-value"):
        assert not any(text in line for line in lines), text


@pytest.mark.parametrize("status", [400, 401])
async def test_a_refused_refresh_ends_the_run_for_good(workspace, memory_jobs, google, status):
    setup = await setup_run(workspace, memory_jobs, cred=credential(expired=True))
    google.fail["oauth2"] = failed("http_4xx", status, True)
    _response, log = await run_one(setup)
    assert (await run(log)).status == "failed"
    done = await container.action_log_repo().get(log.id)
    assert done.last_error_code == "oauth_token_missing" and done.attempts == 1
    assert google.appends() == []


async def test_no_credential_or_one_no_key_opens_is_permanent(workspace, memory_jobs, google):
    setup = await setup_run(workspace, memory_jobs)
    document = await container.form_repo().get_form_document_by_id(setup.form.form_id)
    document.secrets = {str(setup.action.id): [ParameterValue(name="Credentials", value="not-sealed")]}
    await container.form_repo().save_form(document)
    _response, log = await run_one(setup)
    assert (await run(log)).status == "failed"
    assert (await container.action_log_repo().get(log.id)).last_error_code == "secret_unreadable"
    assert google.calls == []


# ------------------------------------------------------------ errors, retry


@pytest.mark.parametrize(
    "status, code",
    [(404, "sheet_missing"), (403, "sheet_access_denied"), (401, "oauth_token_missing")],
)
async def test_a_permanent_answer_ends_the_run_and_is_not_retried(
    workspace, memory_jobs, google, status, code
):
    setup = await setup_run(workspace, memory_jobs)
    google.fail["values"] = failed("http_4xx", status, True)
    _response, log = await run_one(setup)
    assert (await run(log)).status == "failed"
    done = await container.action_log_repo().get(log.id)
    assert done.status is LogStatus.FAILED and done.last_error_code == code and done.attempts == 1


async def test_a_server_error_is_retried_5_then_25_seconds_then_ends_visible(
    workspace, memory_jobs, google
):
    setup = await setup_run(workspace, memory_jobs)
    google.fail["values"] = failed("http_5xx", 503, False)
    _response, log = await run_one(setup)
    waits = []
    for attempt in (1, 2):
        outcome = await run(log)
        assert outcome.status == "retrying" and outcome.retry
        log = await container.action_log_repo().get(log.id)
        waits.append(round((log.next_attempt_at - log.last_attempt_at).total_seconds()))
    assert waits == [5, 25]
    assert (await run(log)).status == "failed"  # the third attempt is the last
    done = await container.action_log_repo().get(log.id)
    assert done.attempts == 3 and done.last_error_code == "http_5xx" and done.last_http_status == 503


async def test_the_retry_schedule_of_the_job():
    strategy = sheets.SheetsRetryStrategy()
    decide = lambda attempts, **kw: strategy.get_retry_decision(  # noqa: E731
        exception=sheets.SheetsRetry(**kw), job=SimpleNamespace(attempts=attempts)
    )
    def seconds(decision):
        return round((decision.retry_at - dt.datetime.now(dt.timezone.utc)).total_seconds())

    assert seconds(decide(0)) == 5
    assert seconds(decide(1)) == 25
    assert seconds(decide(1, retry_after=60)) == 60
    assert decide(2) is None


@pytest.mark.parametrize(
    "bad", ["../../etc/passwd", "short", "a" * 20 + "/../x", "x" * 101, "id with space" + "y" * 20, ""]
)
async def test_a_spreadsheet_id_that_is_not_one_is_refused_before_any_call(
    workspace, memory_jobs, google, bad
):
    setup = await setup_run(workspace, memory_jobs, sheet_id=bad)
    _response, log = await run_one(setup)
    assert (await run(log)).status == "failed"
    assert (await container.action_log_repo().get(log.id)).last_error_code == "sheet_id_invalid"
    assert google.calls == []


async def test_a_call_to_any_other_host_is_refused():
    api = sheets.GoogleApi(lambda *a, **k: pytest.fail("a request was made"))
    with pytest.raises(client.SendFailed) as refused:
        await api._call("GET", "https://evil.example/v4/spreadsheets/x", token="t")
    assert refused.value.code == "config_invalid" and refused.value.permanent


# ----------------------------------------------------------- what stops a run


async def test_an_erased_response_is_never_appended(workspace, memory_jobs, google):
    setup = await setup_run(workspace, memory_jobs)
    response, log = await run_one(setup)
    await container.form_response_service()._form_response_repo.delete_response(
        response_id=response.response_id
    )
    assert (await run(log)).status == "gone"  # erasure wins over a late run
    assert google.calls == [] and await runs_of(setup.form) == []


async def test_erasing_a_response_through_the_service_removes_its_run_row(
    workspace, memory_jobs, google
):
    setup = await setup_run(workspace, memory_jobs)
    response, _log = await run_one(setup)
    await container.form_response_service().delete_form_response(
        form_id=setup.form.form_id, response_id=response.response_id, workspace_id=workspace.id
    )
    assert await runs_of(setup.form) == []


async def test_an_action_switched_off_or_no_longer_marked_cancels_the_run(
    workspace, memory_jobs, google
):
    setup = await setup_run(workspace, memory_jobs)
    _response, log = await run_one(setup)
    document = await container.form_repo().get_form_document_by_id(setup.form.form_id)
    document.actions[Trigger.on_submit][0].migrated_to = None  # given back to the executor
    await container.form_repo().save_form(document)
    assert (await run(log)).status == "cancelled"
    assert (await container.action_log_repo().get(log.id)).last_error_code == "disabled"
    assert google.calls == []


async def test_a_run_whose_job_was_never_queued_is_queued_again(workspace, memory_jobs, google):
    setup = await setup_run(workspace, memory_jobs)
    _response, log = await run_one(setup)
    memory_jobs.jobs.clear()
    from tests.app.email_actions.helpers import age

    await age(log, dt.timedelta(minutes=10))
    counts = await container.sheets_run_service().redefer_pending()
    assert counts == {"queued": 1, "rescued": 0, "failed": 0}
    assert [j["task_name"] for j in memory_jobs.jobs.values()] == ["run_sheets_append"]


async def test_the_sheets_log_rows_are_not_listed_as_webhook_deliveries(workspace, memory_jobs, google):
    setup = await setup_run(workspace, memory_jobs)
    await run_one(setup)
    listed = await container.action_log_repo().list_for_form(workspace.id, setup.form.form_id)
    assert listed == []


# ------------------------------------------------------- the real client


async def test_through_the_pinned_client_the_calls_are_plain_requests_to_googles_host(monkeypatch):
    from backend.app.services.registration.client import PinnedBackend
    from tests.app.registration.tls_server import PUBLIC_ADDRESS, DialToServer, TlsServer

    async with TlsServer("sheets.googleapis.com") as server:
        async def resolve(name, port=443):
            return [PUBLIC_ADDRESS]

        monkeypatch.setattr(client, "resolve", resolve)
        monkeypatch.setattr(
            client, "network_backend",
            lambda name, address: PinnedBackend(name, address, inner=DialToServer(server)),
        )
        monkeypatch.setattr(client, "ssl_context", server.client_context)
        server.script.answers = [(200, {}, json.dumps({"values": [["A", "B"]]}).encode())]
        api = sheets.GoogleApi()
        assert await api.first_row(SHEET, "tok") == ["A", "B"]
        (request,) = server.requests
        assert request.method == "GET"
        assert request.target == f"/v4/spreadsheets/{SHEET}/values/A1%3A1"
        assert request.headers["authorization"] == "Bearer tok"
        server.script.answers = [(200, {}, b"{}")]
        await api.append(SHEET, "tok", "'Tab name'!A2", [["x"]])
        second = server.requests[1]
        assert second.method == "POST"
        assert second.target.startswith(f"/v4/spreadsheets/{SHEET}/values/%27Tab%20name%27%21A2:append?")
        assert "valueInputOption=USER_ENTERED" in second.target
        assert second.headers["content-type"] == "application/json"
        # a refused status maps to our codes
        server.script.answers = [(404, {}, b"{}")]
        with pytest.raises(client.SendFailed) as gone:
            await api.first_row(SHEET, "tok")
        assert gone.value.code == "sheet_missing" and gone.value.permanent


# ------------------------------------------------------------------- the worker


def test_the_worker_serves_the_integrations_queue_and_warns_when_it_does_not():
    from backend.jobs import worker
    from backend.jobs.app import INTEGRATIONS_QUEUE

    assert worker.warn_if_integrations_unserved(["default", "integrations"]) is False
    assert worker.warn_if_integrations_unserved(["default"]) is True
    assert tasks.run_sheets_append.queue == INTEGRATIONS_QUEUE
    assert tasks.sheets_redefer.queue == INTEGRATIONS_QUEUE
    import inspect

    assert "INTEGRATIONS_QUEUE}" in inspect.getsource(worker.main)


async def test_a_run_whose_last_attempt_died_ends_failed_and_one_with_attempts_left_goes_again(
    workspace, memory_jobs, google
):
    from backend.app.schemas.webhook import LogStatus as Status
    setup = await setup_run(workspace, memory_jobs)
    _first, last = await run_one(setup)
    _second, spare = await run_one(setup)
    repo = container.action_log_repo()
    for row, attempts in ((last, sheets.MAX_ATTEMPTS), (spare, 1)):
        stuck = await repo.get(row.id)
        stuck.status = Status.IN_PROGRESS
        stuck.attempts = attempts
        await repo.save_existing(stuck)
    memory_jobs.jobs.clear()
    service = container.sheets_run_service()
    original = service._clock
    service._clock = lambda: original() + dt.timedelta(hours=2)  # two hours on
    try:
        counts = await service.redefer_pending()
    finally:
        service._clock = original
    assert counts == {"queued": 0, "rescued": 1, "failed": 1}
    ended = await repo.get(last.id)
    assert ended.status is Status.FAILED and ended.last_error_code == "worker_lost" and ended.finished_at
    assert (await repo.get(spare.id)).status is Status.PENDING
    assert [j["args"]["log_id"] for j in memory_jobs.jobs.values()] == [str(spare.id)]
    # the failed one is not queued again by the next sweep (the other one is pending)
    memory_jobs.jobs.clear()
    service._clock = lambda: original() + dt.timedelta(hours=3)
    try:
        again = await service.redefer_pending()
    finally:
        service._clock = original
    assert again["failed"] == 0 and str(last.id) not in {j["args"]["log_id"] for j in memory_jobs.jobs.values()}


async def test_a_question_title_is_written_as_it_is_never_as_a_formula(workspace, memory_jobs, google):
    fields = [{"id": "name", "type": "short_text", "title": "=HYPERLINK(\"http://x\")"}]
    form = await publish(workspace, fields=fields)
    action = await attach(workspace, form)
    setup = SimpleNamespace(workspace=workspace, form=form, action=action)
    _response, log = await run_one(setup, answers={"name": {"type": "text", "text": "=1+1"}})
    assert (await run(log)).status == "delivered"
    header_writes = [c for c in google.calls if c.url.endswith("values:batchUpdate")]
    assert json.loads(header_writes[0].body)["valueInputOption"] == "RAW"
    assert google.tabs["Sheet1"]["header"] == ['=HYPERLINK("http://x")']  # no apostrophe: RAW keeps it text
    (row,) = google.tabs["Sheet1"]["rows"]
    assert row == ["'=1+1"]  # an answer is still guarded
    appends = google.appends()
    assert json.loads(appends[0].body)["values"] == [["'=1+1"]]
    assert appends[0].query["valueInputOption"] == "USER_ENTERED"
