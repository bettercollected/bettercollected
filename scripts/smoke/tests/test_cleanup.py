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

NOW = dt.datetime(2026, 10, 31, 12, 0, tzinfo=dt.timezone.utc)
OLD = (NOW - dt.timedelta(days=3)).isoformat()
FRESH = (NOW - dt.timedelta(minutes=5)).isoformat()


class FakeKey:
    """The public API with a key: records every call, deletes what it is told
    to, and can refuse deletes."""

    def __init__(self, existing=None, delete_error=None, spec_purpose=None):
        self.existing = list(existing or [])
        self.delete_error = delete_error
        self.spec_purpose = spec_purpose or {}
        self.created = []
        self.deleted = []
        self.calls = []

    def get(self, path, **kwargs):
        self.calls.append(("GET", path))
        if path.startswith("/forms?"):
            page = int(path.split("page=")[1].split("&")[0])
            return Reply(200, {}, {"items": self.existing if page == 1 else []})
        form_id = path.split("/forms/")[1].split("?")[0]
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


def listed(form_id, title, updated=OLD, slug="slug"):
    return {"formId": form_id, "title": title, "slug": slug, "updatedAt": updated}


class FakeApi:
    def __init__(self, workspace_ok=True):
        self.workspace_ok = workspace_ok

    def get(self, path, **kwargs):
        if path.startswith("/workspaces?workspace_name="):
            return Reply(200, {}, {"id": "a" * 24})
        if path.startswith("/workspaces/") and "/forms/" in path:
            if self.workspace_ok:
                return Reply(200, {}, {})
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
    assert "1 skipped" in "\n".join(lines)


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
