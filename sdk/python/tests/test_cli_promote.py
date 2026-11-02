"""``bettercollected create`` and ``promote`` against two mocked workspaces."""

import io
import json
import os

import httpx
import pytest

from bettercollected import cli
from bettercollected.client import BetterCollected
from tests.fake_api import FakeApi

STAGING_KEY = "bc_" + "1" * 64
PRODUCTION_KEY = "bc_" + "2" * 64
STAGING_URL = "https://staging.forms.example.org"
PRODUCTION_URL = "https://forms.example.org"
FOREIGN_IMAGE = "https://s3.staging.example/bucket/media_library/ws/a.png"

SOURCE = {
    "specVersion": "1",
    "title": "Event sign-up",
    "welcomePage": {"title": "Hi", "imageUrl": FOREIGN_IMAGE},
    "pages": [
        {
            "id": "page-1",
            "fields": [
                {"id": "name", "type": "short_text", "title": "Your name"},
                {
                    "id": "city",
                    "type": "dropdown",
                    "title": "City",
                    "optionSource": {"kind": "list", "listId": "L-stg"},
                },
                {
                    "id": "who",
                    "type": "multiple_choice",
                    "title": "Who",
                    "optionSource": {
                        "kind": "form_answers",
                        "formId": "F",
                        "questionId": "q",
                    },
                },
            ],
        }
    ],
    "trust": {
        "purpose": "Staging purpose",
        "retention": {"type": "days", "value": 3},
        "allowSaveDraft": False,
    },
}

PRODUCTION_FORM = {
    "specVersion": "1",
    "title": "Event sign-up",
    "pages": [
        {
            "id": "page-1",
            "fields": [{"id": "name", "type": "short_text", "title": "Name"}],
        }
    ],
    "trust": {"purpose": "Production purpose", "retention": {"type": "days", "value": 365}},
}


class World:
    """Two workspaces on two instances, reached through one factory."""

    def __init__(self) -> None:
        self.staging = FakeApi(STAGING_KEY)
        self.production = FakeApi(PRODUCTION_KEY)
        self.staging.add("s1", SOURCE)
        self.production.add("p1", PRODUCTION_FORM)

    def client(self, key, url):
        fake = {STAGING_KEY: self.staging, PRODUCTION_KEY: self.production}[key]
        return BetterCollected(key, url, transport=fake.transport())

    @property
    def requests(self):
        return self.staging.requests + self.production.requests

    def writes(self, fake):
        """Requests that store something (validate and dry-run only check)."""
        return [
            r
            for r in fake.requests
            if r.method in ("POST", "PUT", "PATCH", "DELETE")
            and not r.url.path.endswith(("/validate", "/dry-run"))
        ]


@pytest.fixture
def world(monkeypatch, tmp_path):
    world = World()
    for name, value in {
        "BETTERCOLLECTED_STAGING_API_KEY": STAGING_KEY,
        "BETTERCOLLECTED_STAGING_URL": STAGING_URL,
        "BETTERCOLLECTED_PRODUCTION_API_KEY": PRODUCTION_KEY,
        "BETTERCOLLECTED_PRODUCTION_URL": PRODUCTION_URL,
    }.items():
        monkeypatch.setenv(name, value)
    for name in (cli.API_KEY_ENV, cli.URL_ENV, cli.CONFIG_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-config"))
    monkeypatch.setattr(cli, "BetterCollected", world.client)
    monkeypatch.chdir(tmp_path)
    return world


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def promote(*extra, form="s1"):
    return run("promote", form, "--from", "staging", "--to", "production", *extra)


def test_promote_creates_a_new_draft_and_never_publishes(world):
    code, out, err = promote()
    assert code == 0, out + err
    created = world.production.forms["f2"]
    assert created["title"] == "Event sign-up"
    # normalised for the other instance
    assert "imageUrl" not in created["welcomePage"]
    city = created["pages"][0]["fields"][1]
    assert "optionSource" not in city
    assert "optionSource" not in created["pages"][0]["fields"][2]
    # a new form takes the source's trust settings
    assert created["trust"]["purpose"] == "Staging purpose"
    # the source is untouched and only the production side was written
    assert world.staging.forms["s1"] == SOURCE
    assert world.writes(world.staging) == []
    assert [r.url.path.rsplit("/", 1)[-1] for r in world.writes(world.production)] == [
        "forms"
    ]
    assert not any("publish" in r.url.path for r in world.requests)
    assert "Created draft f2" in out and "publish it in the target" in out


def test_the_output_has_counts_and_never_urls_or_keys(world):
    code, out, err = promote()
    assert code == 0
    assert "1 image(s) dropped" in out
    assert "option source(s) taken from another form's answers dropped" in out
    assert "Never copied:" in out and "responses (answers are never copied)" in out
    for secret in (STAGING_KEY, PRODUCTION_KEY, "staging.example", "forms.example.org"):
        assert secret not in out + err


def test_dry_run_writes_nothing(world):
    code, out, _ = promote("--dry-run")
    assert code == 0
    assert "A new draft with 1 page(s) and 3 question(s)." in out
    assert "Dry run: nothing was written." in out
    assert set(world.production.forms) == {"p1"}
    assert [r.url.path.rsplit("/", 1)[-1] for r in world.production.requests] == [
        "validate"
    ]


def test_an_existing_target_is_updated_as_a_draft_and_keeps_its_data_protection(world):
    code, out, err = promote("--to-form", "p1")
    assert code == 0, out + err
    updated = world.production.forms["p1"]
    assert [f["id"] for f in updated["pages"][0]["fields"]] == ["name", "city", "who"]
    # the retention and purpose of production stay; the rest of trust moves
    assert updated["trust"]["purpose"] == "Production purpose"
    assert updated["trust"]["retention"] == {"type": "days", "value": 365}
    assert updated["trust"]["allowSaveDraft"] is False
    assert "The target form keeps its own purpose, retention" in out
    # the diff is shown before the write, with the If-Match of the reviewed version
    assert "+ field city" in out and "Changes to the draft of p1:" in out
    put = [r for r in world.production.requests if r.method == "PUT"]
    assert len(put) == 1 and put[0].headers["If-Match"] == '"1-test"'
    assert "Updated the draft of p1." in out


def test_copy_privacy_takes_the_sources_settings_and_warns_when_shorter(world):
    code, out, _ = promote("--to-form", "p1", "--copy-privacy")
    assert code == 0
    trust = world.production.forms["p1"]["trust"]
    assert trust["purpose"] == "Staging purpose"
    assert trust["retention"] == {"type": "days", "value": 3}
    assert "warning: --copy-privacy changes how long the target keeps answers" in out


def test_a_second_promotion_with_nothing_new_changes_nothing(world):
    assert promote("--to-form", "p1")[0] == 0
    before = len(world.writes(world.production))
    code, out, _ = promote("--to-form", "p1")
    assert code == 0 and "No changes" in out
    assert len(world.writes(world.production)) == before


def test_dry_run_against_an_existing_form_shows_the_diff_only(world):
    code, out, _ = promote("--to-form", "p1", "--dry-run")
    assert code == 0 and "+ field city" in out and "Dry run" in out
    assert world.production.forms["p1"] == PRODUCTION_FORM
    assert world.writes(world.production) == []


def test_what_the_target_refuses_is_listed_and_nothing_is_written(world):
    world.production.refuse_types = ("dropdown",)
    code, out, _ = promote()
    assert code == 1
    assert "would refuse this form (1 problem(s)); nothing was written" in out
    assert "/pages/0/fields/1/type: dropdown questions are not enabled here." in out
    assert set(world.production.forms) == {"p1"}

    code, out, _ = promote("--to-form", "p1")
    assert code == 1 and "/pages/0/fields/1/type" in out
    assert world.production.forms["p1"] == PRODUCTION_FORM


def test_a_target_that_changed_during_review_is_not_overwritten(world, monkeypatch):
    original = world.production.handle

    def changing(request):
        response = original(request)
        if request.url.path.endswith("dry-run"):
            world.production.change_on_server("p1", title="Edited meanwhile")
        return response

    monkeypatch.setattr(world.production, "handle", changing)
    code, _, err = promote("--to-form", "p1")
    assert code == 1 and "changed while you were reviewing" in err
    assert world.production.forms["p1"]["title"] == "Edited meanwhile"


def test_two_workspaces_of_one_instance_share_image_storage(world, monkeypatch):
    monkeypatch.setenv("BETTERCOLLECTED_PRODUCTION_URL", STAGING_URL)
    code, _, _ = promote()
    assert code == 0
    assert (
        world.production.forms["f2"]["welcomePage"]["imageUrl"] == FOREIGN_IMAGE
    )


def test_a_list_map_matches_option_lists(world, tmp_path):
    (tmp_path / "lists.json").write_text(json.dumps({"L-stg": "L-prod"}))
    code, out, _ = promote("--list-map", "lists.json")
    assert code == 0
    city = world.production.forms["f2"]["pages"][0]["fields"][1]
    assert city["optionSource"] == {"kind": "list", "listId": "L-prod"}
    assert "1 option list(s) matched" in out

    (tmp_path / "bad.json").write_text("[1]")
    code, _, err = promote("--list-map", "bad.json")
    assert code == 1 and "must hold an object of option list ids" in err


def test_the_same_form_cannot_be_promoted_onto_itself(world, monkeypatch):
    monkeypatch.setenv("BETTERCOLLECTED_PRODUCTION_API_KEY", STAGING_KEY)
    monkeypatch.setenv("BETTERCOLLECTED_PRODUCTION_URL", STAGING_URL)
    code, _, err = promote("--to-form", "s1")
    assert code == 1 and "same form" in err
    assert world.requests == []


def test_a_missing_source_form_is_reported(world):
    code, _, err = promote(form="nope")
    assert code == 1 and "Form not found" in err
    assert world.writes(world.production) == []


def test_only_the_two_configured_instances_are_called(world):
    promote()
    hosts = {str(r.url.host) for r in world.requests}
    assert hosts <= {"staging.forms.example.org", "forms.example.org"}
    assert {r.headers["Authorization"] for r in world.staging.requests} == {
        f"Bearer {STAGING_KEY}"
    }
    assert {r.headers["Authorization"] for r in world.production.requests} == {
        f"Bearer {PRODUCTION_KEY}"
    }


# -- keys ----------------------------------------------------------------------


def test_a_key_cannot_be_given_on_the_command_line(world, capsys):
    for flag in ("--api-key", "--key", "--to-key", "--from-key"):
        with pytest.raises(SystemExit) as stopped:
            cli.main(["promote", "s1", "--to", "production", flag, PRODUCTION_KEY])
        assert stopped.value.code == 2
    assert PRODUCTION_KEY not in capsys.readouterr().out


def test_a_missing_key_says_which_variable_to_set(world, monkeypatch):
    monkeypatch.delenv("BETTERCOLLECTED_PRODUCTION_API_KEY")
    code, _, err = promote()
    assert code == 1 and "BETTERCOLLECTED_PRODUCTION_API_KEY" in err
    assert world.requests == []


def test_the_default_environment_is_the_plain_key_and_url(world, monkeypatch):
    monkeypatch.setenv(cli.API_KEY_ENV, STAGING_KEY)
    monkeypatch.setenv(cli.URL_ENV, STAGING_URL)
    code, out, _ = run("promote", "s1", "--to", "production")
    assert code == 0 and "default -> production" in out


def test_the_environment_does_not_show_its_key():
    environment = cli.Environment("production", PRODUCTION_URL, PRODUCTION_KEY)
    assert PRODUCTION_KEY not in repr(environment)


def test_config_file_names_a_variable_for_the_key(world, monkeypatch, tmp_path):
    monkeypatch.delenv("BETTERCOLLECTED_PRODUCTION_API_KEY")
    monkeypatch.delenv("BETTERCOLLECTED_PRODUCTION_URL")
    monkeypatch.setenv("PROD_KEY", PRODUCTION_KEY)
    config = tmp_path / "environments.yaml"
    config.write_text(
        "environments:\n  production:\n"
        f"    url: {PRODUCTION_URL}\n    api_key_env: PROD_KEY\n"
    )
    code, out, err = promote("--config", str(config))
    assert code == 0, out + err
    assert "f2" in world.production.forms


def test_a_key_written_in_the_config_file_needs_a_private_file(
    world, monkeypatch, tmp_path
):
    monkeypatch.delenv("BETTERCOLLECTED_PRODUCTION_API_KEY")
    config = tmp_path / "environments.yaml"
    config.write_text(
        f"environments:\n  production:\n    url: {PRODUCTION_URL}\n"
        f"    api_key: {PRODUCTION_KEY}\n"
    )
    if os.name == "posix":
        config.chmod(0o644)
        code, out, err = promote("--config", str(config))
        assert code == 1 and "chmod 600" in err
        assert PRODUCTION_KEY not in out + err
        assert world.requests == []
        config.chmod(0o600)
    code, out, err = promote("--config", str(config))
    assert code == 0, out + err


def test_a_named_config_file_must_exist(world, monkeypatch, tmp_path):
    monkeypatch.delenv("BETTERCOLLECTED_PRODUCTION_API_KEY")
    code, _, err = promote("--config", str(tmp_path / "missing.yaml"))
    assert code == 1 and "does not exist" in err


def test_a_network_failure_does_not_print_the_key(world, monkeypatch):
    def broken(key, url):
        def refuse(request):
            raise httpx.ConnectError("connection refused")

        return BetterCollected(key, url, transport=httpx.MockTransport(refuse))

    monkeypatch.setattr(cli, "BetterCollected", broken)
    code, out, err = promote()
    assert code == 1 and "the request failed (ConnectError" in err
    assert STAGING_KEY not in out + err


# -- create --------------------------------------------------------------------


def test_create_makes_a_draft_from_a_file_and_remembers_it(world, monkeypatch, tmp_path):
    monkeypatch.setenv(cli.API_KEY_ENV, PRODUCTION_KEY)
    monkeypatch.setenv(cli.URL_ENV, PRODUCTION_URL)
    (tmp_path / "form.json").write_text(json.dumps(PRODUCTION_FORM))
    code, out, _ = run("create", "form.json", "--idempotency-key", "k1")
    assert code == 0 and "Created draft f2" in out and "not published" in out
    request = world.production.requests[-1]
    assert request.headers["Idempotency-Key"] == "k1"
    assert not any("publish" in r.url.path for r in world.requests)
    state = json.loads((tmp_path / ".bettercollected.json").read_text())
    assert state["forms"]["form.json"]["formId"] == "f2"
    assert PRODUCTION_KEY not in (tmp_path / ".bettercollected.json").read_text()
    # a file that belongs to a form is changed with push, not created again
    code, _, err = run("create", "form.json")
    assert code == 1 and "use push" in err
    assert set(world.production.forms) == {"p1", "f2"}


def test_create_reports_what_the_server_refuses(world, monkeypatch, tmp_path):
    monkeypatch.setenv(cli.API_KEY_ENV, PRODUCTION_KEY)
    monkeypatch.setenv(cli.URL_ENV, PRODUCTION_URL)
    world.production.refuse_types = ("short_text",)
    (tmp_path / "form.json").write_text(json.dumps(PRODUCTION_FORM))
    code, _, err = run("create", "form.json")
    assert code == 1 and "/pages/0/fields/0/type" in err
    assert not (tmp_path / ".bettercollected.json").exists()
