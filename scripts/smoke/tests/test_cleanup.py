"""The run's own cleanup and the one-off cleanup, against a mocked API client."""

import datetime as dt
import json

import pytest

from smoke import cleanup, config as config_module, forms
from smoke.checks import Suite
from smoke.http import HttpError, Reply
from smoke.redact import Redactor
from smoke.report import Abort, Report
from tests.conftest import API_KEY

# The real clock: the command-line tests go through cleanup.main(), which reads
# it too, so a fixed date here would make FRESH forms stale as time passes.
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
OLD = (NOW - dt.timedelta(days=3)).isoformat()
FRESH = (NOW - dt.timedelta(minutes=5)).isoformat()


class FakeKey:
    """The public API with a key: records every call, deletes what it is told
    to, and can refuse deletes."""

    def __init__(
        self, existing=None, delete_error=None, spec_purpose=None, pages=None, gone=()
    ):
        self.existing = list(existing or [])
        self.pages = pages  # a server that answers short pages
        self.gone = set(gone)
        self.delete_error = delete_error
        self.spec_purpose = spec_purpose or {}
        self.created = []
        self.deleted = []
        self.calls = []

    def get(self, path, **kwargs):
        self.calls.append(("GET", path))
        if path.startswith("/forms?"):
            page = int(path.split("page=")[1].split("&")[0])
            if self.pages is not None:
                batch = self.pages[page - 1] if page <= len(self.pages) else []
                total = sum(len(p) for p in self.pages) + 1  # one entry has no form row
                return Reply(200, {}, {"items": batch, "total": total})
            batch = self.existing if page == 1 else []
            return Reply(200, {}, {"items": batch, "total": len(self.existing)})
        form_id = path.split("/forms/")[1].split("?")[0]
        if form_id in self.gone:
            raise HttpError("GET", path, 404, "not_found")
        item = next(f for f in self.existing if f["formId"] == form_id)
        purpose = self.spec_purpose.get(form_id, forms.PURPOSE)
        return Reply(
            200, {}, {"title": item["title"], "trust": {"purpose": purpose}}
        )

    def post(self, path, body=None, **kwargs):
        self.calls.append(("POST", path))
        if path == "/forms":
            form_id = f"{len(self.created) + 1:024x}"
            self.created.append(form_id)
            self.existing.append(
                {"formId": form_id, "title": body["title"], "slug": f"s-{form_id}"}
            )
            return Reply(201, {}, {"formId": form_id})
        if path.endswith("/publish"):
            return Reply(200, {}, {"slug": "a-slug"})
        raise AssertionError(path)

    def delete(self, path, **kwargs):
        self.calls.append(("DELETE", path))
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(path.rsplit("/", 1)[1])
        return Reply(204, {}, None)


def scope_error(form_id="x"):
    return HttpError("DELETE", f"/forms/{form_id}", 403, "missing_scope")


# -- delete_forms ---------------------------------------------------------------
def test_delete_forms_deletes_exactly_the_given_ids():
    key = FakeKey()
    result = cleanup.delete_forms(key, [("a" * 24, "run form"), ("b" * 24, "run form")])
    assert key.deleted == ["a" * 24, "b" * 24]
    assert [c[0] for c in key.calls] == ["DELETE", "DELETE"]
    assert not result.left


def test_an_empty_or_repeated_id_is_not_deleted_twice():
    key = FakeKey()
    cleanup.delete_forms(key, [("", "x"), ("a" * 24, "x"), ("a" * 24, "x")])
    assert key.deleted == ["a" * 24]


def test_a_missing_scope_is_reported_with_the_ids_left_behind():
    key = FakeKey(delete_error=scope_error())
    result = cleanup.delete_forms(key, [("a" * 24, "run form"), ("b" * 24, "run form")])
    assert result.missing_scope and not result.deleted
    # one refused call is enough: the second form is not tried
    assert len(key.calls) == 1
    notes, warnings = cleanup.describe(result)
    assert len(warnings) == 1
    assert "forms:delete" in warnings[0]
    assert "a" * 24 in warnings[0] and "b" * 24 in warnings[0]
    assert "python -m smoke.cleanup" in warnings[0]


def test_another_error_does_not_stop_the_rest():
    class Flaky(FakeKey):
        def delete(self, path, **kwargs):
            if path.endswith("a" * 24):
                raise HttpError("DELETE", path, 500)
            return super().delete(path)

    key = Flaky()
    result = cleanup.delete_forms(key, [("a" * 24, "x"), ("b" * 24, "x")])
    assert key.deleted == ["b" * 24]
    assert [fid for fid, _, _ in result.left] == ["a" * 24]
    assert cleanup.describe(result)[1]


def test_a_form_that_is_already_gone_is_not_a_problem():
    key = FakeKey(delete_error=HttpError("DELETE", "/forms/x", 404))
    result = cleanup.delete_forms(key, [("a" * 24, "run form")])
    assert result.already_gone and not result.left
    assert cleanup.describe(result)[1] == []


# -- the suite's cleanup ----------------------------------------------------------
class NoMailbox:
    def cleanup(self, address):
        return "mailbox cleaned"

    def close(self):
        pass


def make_suite(base_env, key, **patches):
    config = config_module.load(
        base_env, mailpit_url="http://localhost:8025", tag="smoke-local-abc123"
    )
    report = Report(Redactor([API_KEY]), config.app_url, config.run_tag)
    suite = Suite(config, report, NoMailbox(), playwright=None)
    suite.key = key
    suite.api = object()
    # the checks that need a browser, a mailbox or the network
    for name in (
        "check_public_endpoints",
        "check_standing_set",
        "check_sign_in",
        "check_custom_domain",
        "check_deletion_request",
        "check_google_import",
    ):
        setattr(suite, name, patches.get(name, lambda: None))
    return suite


def browser_step_fails():
    raise RuntimeError("the browser step failed")


def test_the_run_form_is_deleted_even_when_a_step_fails(base_env):
    other = {"formId": "f" * 24, "title": "A real form", "slug": "real"}
    key = FakeKey(existing=[other])
    suite = make_suite(base_env, key)
    suite.session = browser_step_fails  # check 2 creates the form, then fails
    suite.run()
    round_trip = next(c for c in suite.report.checks if c.number == "2")
    assert round_trip.status == "fail"
    assert key.created and key.deleted == key.created
    assert "f" * 24 not in key.deleted
    assert any("deleted" in line for line in suite.report.cleanup)


def test_a_later_check_that_blows_up_still_cleans_up(base_env):
    key = FakeKey()
    suite = make_suite(base_env, key)
    suite.session = browser_step_fails

    def explodes():
        raise Abort("stop here")

    suite.check_custom_domain = explodes
    suite.run()
    assert key.created and key.deleted == key.created


def test_a_failure_before_anything_was_created_deletes_nothing(base_env):
    key = FakeKey(existing=[{"formId": "f" * 24, "title": "Real", "slug": "real"}])

    def abort():
        raise Abort("the public endpoints do not answer")

    suite = make_suite(base_env, key, check_public_endpoints=abort)
    suite.run()
    assert key.deleted == []
    assert not [c for c in key.calls if c[0] == "DELETE"]


def test_an_unfinished_standing_form_is_deleted_but_a_found_one_is_kept(base_env):
    # the set is made this run, then the workspace check stops the run
    key = FakeKey()
    suite = make_suite(base_env, key, check_standing_set=lambda: None)
    del suite.check_standing_set  # use the real check
    suite._in_workspace = lambda slug: False
    suite.run()
    assert len(key.created) == 1 and key.deleted == key.created

    # an existing standing form is read, never deleted
    standing = {
        "formId": "5" * 24,
        "title": forms.STANDING_TITLE,
        "slug": "standing",
    }
    key = FakeKey(existing=[standing])
    suite = make_suite(base_env, key)
    del suite.check_standing_set
    suite._in_workspace = lambda slug: False  # stops the run right after
    suite.run()
    assert key.deleted == []


def test_a_missing_scope_is_a_warning_and_the_run_still_passes(base_env):
    key = FakeKey(delete_error=scope_error())
    suite = make_suite(base_env, key)
    suite.state.created.clear()

    def round_trip_without_browser():
        suite.state.created["c" * 24] = "run form"

    suite.check_form_round_trip = round_trip_without_browser
    suite.run()
    assert suite.report.ok
    assert len(suite.report.warnings) == 1
    assert "forms:delete" in suite.report.warnings[0]
    assert "c" * 24 in suite.report.warnings[0]
    assert "**Warning:**" in suite.report.markdown()
    assert json.loads(json.dumps(suite.report.as_dict()))["warnings"]


# -- the one-off cleanup ------------------------------------------------------------
RUN_TITLE = forms.run_title("smoke-123456-1-0a1b2c")
LOCAL_TITLE = forms.run_title("smoke-local-0a1b2c")


def listed(form_id, title, updated=OLD, slug="default"):
    if slug == "default":
        slug = f"s-{form_id}"
    return {"formId": form_id, "title": title, "slug": slug, "updatedAt": updated}


class FakeApi:
    """The app's API: the configured workspace holds the forms whose slug is
    ``s-<form id>``; ``other`` maps a slug to the id of a different form (the
    same slug taken by another form of the workspace)."""

    def __init__(self, workspace_ok=True, other=None):
        self.workspace_ok = workspace_ok
        self.other = other or {}

    def get(self, path, **kwargs):
        if path.startswith("/workspaces?workspace_name="):
            return Reply(200, {}, {"id": "a" * 24})
        if path.startswith("/workspaces/") and "/forms/" in path:
            slug = path.split("/forms/")[1].split("?")[0]
            if self.workspace_ok and slug.startswith("s-"):
                return Reply(200, {}, {"formId": self.other.get(slug, slug[2:])})
            raise HttpError("GET", path, 404)
        if path.startswith("/workspaces/"):
            return Reply(200, {}, {"id": "a" * 24})
        raise AssertionError(path)


def old_forms_key():
    existing = [
        listed("1" * 24, RUN_TITLE),
        listed("2" * 24, LOCAL_TITLE),
        listed("3" * 24, forms.STANDING_TITLE),
        listed("4" * 24, "Smoke run feedback survey"),  # a real form's title
        listed("5" * 24, RUN_TITLE.replace("0a1b2c", "0a1b2cX")),
        listed("6" * 24, forms.run_title("smoke-999-1-ffffff"), updated=FRESH),
        listed("7" * 24, "Customer survey"),
        # the right title shape, but not made with the suite's purpose text
        listed("8" * 24, forms.run_title("smoke-777-1-abcdef")),
    ]
    return FakeKey(existing=existing, spec_purpose={"8" * 24: "Collecting feedback"})


def test_the_cleanup_is_a_dry_run_unless_the_flag_is_given():
    key, lines = old_forms_key(), []
    code = cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=False, now=NOW, say=lines.append
    )
    assert code == 0
    assert key.deleted == []
    assert not [c for c in key.calls if c[0] == "DELETE"]
    text = "\n".join(lines)
    assert "would delete: " + "1" * 24 in text
    assert "would delete: " + "2" * 24 in text
    assert "Dry run" in text


def test_the_cleanup_deletes_only_forms_with_both_markers_when_asked():
    key, lines = old_forms_key(), []
    code = cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=True, now=NOW, say=lines.append
    )
    assert code == 0
    assert sorted(key.deleted) == ["1" * 24, "2" * 24]
    # not the standing set, not real forms, not a run still in progress, not
    # a look-alike without the purpose text
    for kept in ("3", "4", "5", "6", "7", "8"):
        assert kept * 24 not in key.deleted
    assert "1 skipped (changed in the last 60 min" in "\n".join(lines)


def test_the_cleanup_refuses_when_the_workspace_is_not_the_configured_one():
    key, lines = old_forms_key(), []
    code = cleanup.run_cleanup(
        FakeApi(workspace_ok=False),
        key,
        "smoke-test",
        delete=True,
        now=NOW,
        say=lines.append,
    )
    assert code == 2
    assert key.deleted == []
    assert "not SMOKE_WORKSPACE_ID" in "\n".join(lines)


def test_the_cleanup_with_a_key_without_the_scope_warns_and_exits_1():
    key, lines = old_forms_key(), []
    key.delete_error = scope_error()
    code = cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=True, now=NOW, say=lines.append
    )
    assert code == 1
    text = "\n".join(lines)
    assert "forms:delete" in text and "1" * 24 in text


def test_every_title_the_suite_creates_matches_the_marker():
    for env in ({}, {"GITHUB_RUN_ID": "123456789", "GITHUB_RUN_ATTEMPT": "2"}):
        title = forms.run_title(config_module.run_tag(env))
        assert forms.RUN_TITLE.fullmatch(title), title
        assert forms.is_run_form(title, forms.PURPOSE)
    assert not forms.is_run_form(forms.STANDING_TITLE, forms.PURPOSE)
    assert not forms.is_run_form(RUN_TITLE, "something else")


# -- the command line ---------------------------------------------------------------
@pytest.fixture
def cli(monkeypatch):
    key = old_forms_key()

    def factory(base_url, headers=None, **kwargs):
        return key if base_url.endswith("/public/v1") else FakeApi()

    monkeypatch.setattr(cleanup, "Http", factory)
    return key


ARGS = ["--api-url", "https://admin.example.com/api/v1"]


def cli_env():
    return {"SMOKE_API_KEY": API_KEY, "SMOKE_WORKSPACE_ID": "smoke-test"}


def test_the_command_is_a_dry_run_by_default(cli, capsys):
    assert cleanup.main(ARGS, env=cli_env()) == 0
    assert cli.deleted == []
    out = capsys.readouterr().out
    assert "dry run" in out and API_KEY not in out


def test_the_command_deletes_only_with_the_flag(cli, capsys):
    assert cleanup.main(ARGS + ["--delete"], env=cli_env()) == 0
    assert sorted(cli.deleted) == ["1" * 24, "2" * 24]
    assert API_KEY not in capsys.readouterr().out


def test_the_command_needs_the_key_and_a_workspace(cli, capsys):
    assert cleanup.main(ARGS, env={"SMOKE_WORKSPACE_ID": "smoke-test"}) == 2
    assert cleanup.main(ARGS, env={"SMOKE_API_KEY": API_KEY}) == 2
    assert cli.calls == []
    assert cleanup.main(["--api-url", "http://admin.example.com/api/v1"], env=cli_env()) == 2
    assert cli.calls == []
    assert API_KEY not in capsys.readouterr().err


# -- review follow-ups -----------------------------------------------------------------
def test_unicode_digits_do_not_make_a_run_title():
    # Arabic-Indic digits are \d for str patterns, but no run tag has them
    assert not forms.RUN_TITLE.fullmatch("Smoke run smoke-\u0661\u0662\u0663-\u0661-abcdef")
    assert not forms.is_run_form(
        "Smoke run smoke-\u0661\u0662\u0663-\u0661-abcdef", forms.PURPOSE
    )


def test_a_candidate_without_a_slug_is_skipped_not_deleted():
    key = old_forms_key()
    key.existing[0]["slug"] = None  # 1111...: marked, but not tied to a workspace
    code = cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=True, now=NOW, say=lambda t: None
    )
    assert code == 0
    assert key.deleted == ["2" * 24]


def test_every_candidate_is_checked_against_the_configured_workspace():
    # the slug of 1111... leads to another form: not ours to delete
    key = old_forms_key()
    api = FakeApi(other={"s-" + "1" * 24: "9" * 24})
    cleanup.run_cleanup(
        api, key, "smoke-test", delete=True, now=NOW, say=lambda t: None
    )
    assert key.deleted == ["2" * 24]


def test_nothing_is_deleted_when_no_candidate_can_be_confirmed():
    key, lines = old_forms_key(), []
    for item in key.existing:
        item["slug"] = None
    code = cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=True, now=NOW, say=lines.append
    )
    assert code == 2 and key.deleted == []
    assert "nothing was touched" in "\n".join(lines)


def test_a_form_without_a_readable_time_counts_as_recent():
    key = old_forms_key()
    key.existing[0]["updatedAt"] = None
    key.existing[1]["updatedAt"] = "not a time"
    cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=True, now=NOW, say=lambda t: None
    )
    assert key.deleted == []


def test_a_form_gone_since_the_list_is_skipped_not_fatal():
    key = old_forms_key()
    key.gone = {"1" * 24}
    code = cleanup.run_cleanup(
        FakeApi(), key, "smoke-test", delete=True, now=NOW, say=lambda t: None
    )
    assert code == 0
    assert key.deleted == ["2" * 24]


def test_the_list_is_read_to_its_end_even_when_pages_come_back_short():
    # page 1 holds 99 of its 100 (one entry had no form row), page 2 holds 50
    pages = [[listed("a" * 24, "x")] * 99, [listed("b" * 24, "y")] * 50]
    key = FakeKey(pages=pages)
    assert len(cleanup.list_all_forms(key)) == 149


def test_a_list_too_long_to_read_raises_instead_of_truncating(monkeypatch):
    monkeypatch.setattr(cleanup, "MAX_LIST_PAGES", 2)
    full = [listed("a" * 24, "x")] * 100
    key = FakeKey(pages=[full] * 5)
    with pytest.raises(cleanup.ListTruncated):
        cleanup.list_all_forms(key)


def test_the_suites_form_lookup_reads_short_pages_too(base_env):
    pages = [[listed("a" * 24, "x")] * 99, [listed("b" * 24, "y")] * 5]
    suite = make_suite(base_env, FakeKey(pages=pages))
    assert len(suite._all_forms()) == 104


def test_the_warning_annotations_are_printed_even_when_the_run_blows_up(
    monkeypatch, base_env, tmp_path, capsys
):
    import contextlib
    import types

    from playwright import sync_api

    from smoke import __main__ as entry
    from smoke import checks, mailbox

    for name, value in base_env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SMOKE_IMAP_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        sync_api, "sync_playwright", lambda: contextlib.nullcontext(object())
    )
    monkeypatch.setattr(
        mailbox, "open_mailbox", lambda *a, **k: types.SimpleNamespace(close=lambda: None)
    )

    def blows_up(self):
        self.report.warn("1 form(s) left behind: " + "a" * 24)
        raise RuntimeError("unhandled")

    monkeypatch.setattr(checks.Suite, "run", blows_up)
    with pytest.raises(RuntimeError):
        entry.main(["--report-dir", str(tmp_path)])
    assert "::warning title=Smoke test cleanup::1 form(s) left behind" in capsys.readouterr().out
    assert (tmp_path / "report.json").exists()


# -- the dry run's publish refusal ------------------------------------------------------
def test_a_refused_publish_names_the_missing_workspace_title(base_env):
    class Refusing(FakeKey):
        def post(self, path, body=None, **kwargs):
            if path.endswith("/publish"):
                raise HttpError("POST", path, 422, "form_not_publishable")
            return super().post(path, body, **kwargs)

    suite = make_suite(base_env, Refusing())
    suite.state.workspace_title = ""
    with pytest.raises(Exception) as caught:
        suite._publish("a" * 24)
    assert "workspace_title_missing" in str(caught.value)
    assert "form_not_publishable" in str(caught.value)


def test_the_hint_is_only_for_that_refusal_and_that_cause():
    from smoke.checks import has_workspace_title, publish_refusal_hint

    refused = HttpError("POST", "/forms/x/publish", 422, "form_not_publishable")
    assert "workspace_title_missing" in publish_refusal_hint(refused, "")
    assert "workspace_title_missing" in publish_refusal_hint(refused, " Untitled ")
    assert "workspace_title_missing" not in publish_refusal_hint(refused, "Smoke")
    assert publish_refusal_hint(HttpError("POST", "/x", 403, "missing_scope"), "") == ""
    assert not has_workspace_title("\u200b ")
    assert has_workspace_title("Smoke test workspace")


def test_the_dry_run_workspace_gets_a_title_that_passes_the_publish_check():
    from smoke import devstack
    from smoke.checks import has_workspace_title

    assert has_workspace_title(devstack.WORKSPACE_TITLE)
    body, content_type = devstack.multipart_form({"title": devstack.WORKSPACE_TITLE})
    boundary = content_type.split("boundary=")[1]
    assert f"--{boundary}--".encode() in body
    assert b'name="title"\r\n\r\n' + devstack.WORKSPACE_TITLE.encode() in body
