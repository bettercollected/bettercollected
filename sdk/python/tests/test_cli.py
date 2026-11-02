import io
import json

import pytest
import yaml

from bettercollected import cli
from bettercollected.client import BetterCollected
from tests.fake_api import KEY, FakeApi
from tests.test_client import SPEC


@pytest.fixture
def api(monkeypatch, tmp_path):
    fake = FakeApi()
    fake.add("f1", SPEC)
    monkeypatch.setenv(cli.API_KEY_ENV, KEY)
    monkeypatch.setenv(cli.URL_ENV, "https://forms.example.org")
    monkeypatch.setattr(
        cli,
        "BetterCollected",
        lambda key, url: BetterCollected(key, url, transport=fake.transport()),
    )
    monkeypatch.chdir(tmp_path)
    return fake


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_pull_writes_json_or_yaml_and_remembers_the_version(api, tmp_path):
    assert run("pull", "f1", "-o", "form.json")[0] == 0
    assert json.loads((tmp_path / "form.json").read_text()) == SPEC
    assert run("pull", "f1", "-o", "form.yaml")[0] == 0
    assert yaml.safe_load((tmp_path / "form.yaml").read_text()) == SPEC
    state = json.loads((tmp_path / ".bettercollected.json").read_text())
    assert state["forms"]["form.json"] == {"formId": "f1", "etag": '"1-test"'}
    # the key is never written anywhere
    assert KEY not in (tmp_path / ".bettercollected.json").read_text()


def test_push_uses_the_pulled_version(api, tmp_path):
    run("pull", "f1", "-o", "form.yaml")
    document = yaml.safe_load((tmp_path / "form.yaml").read_text())
    document["title"] = "Renamed"
    (tmp_path / "form.yaml").write_text(yaml.safe_dump(document))

    code, out, _ = run("push", "form.yaml")
    assert code == 0, out
    assert api.forms["f1"]["title"] == "Renamed"
    assert api.requests[-1].headers["If-Match"] == '"1-test"'
    # the new version is remembered: a second push needs no pull
    assert run("push", "form.yaml")[0] == 0


def test_push_refuses_a_stale_file_unless_forced(api, tmp_path):
    run("pull", "f1", "-o", "form.json")
    api.change_on_server("f1", title="Changed elsewhere")
    code, _, err = run("push", "form.json")
    assert code == 1
    assert "changed on the server" in err
    assert api.forms["f1"]["title"] == "Changed elsewhere"

    code, _, _ = run("push", "form.json", "--force")
    assert code == 0
    assert api.forms["f1"]["title"] == "Event sign-up"


def test_push_without_a_pull_needs_force(api, tmp_path):
    (tmp_path / "new.json").write_text(json.dumps(SPEC))
    code, _, err = run("push", "new.json", "--form-id", "f1")
    assert code == 1 and "pull it first" in err
    assert run("push", "new.json", "--form-id", "f1", "--force")[0] == 0


def test_diff_shows_what_push_would_change(api, tmp_path):
    run("pull", "f1", "-o", "form.json")
    assert run("diff", "form.json")[1].strip() == "No changes."
    document = dict(SPEC, title="Renamed")
    (tmp_path / "form.json").write_text(json.dumps(document))
    code, out, _ = run("diff", "form.json")
    assert code == 0
    assert '~ /title: "Event sign-up" -> "Renamed"' in out

    api.change_on_server("f1", description="x")
    assert "changed on the server" in run("diff", "form.json")[1]


def test_validate(api, tmp_path):
    (tmp_path / "ok.json").write_text(json.dumps(SPEC))
    (tmp_path / "bad.json").write_text(json.dumps(dict(SPEC, specVersion="2")))
    assert run("validate", "ok.json")[0] == 0
    code, out, _ = run("validate", "bad.json")
    assert code == 1 and "/specVersion" in out
    (tmp_path / "broken.json").write_text("{")
    code, _, err = run("validate", "broken.json")
    assert code == 1 and "not valid JSON" in err


def test_the_key_comes_from_the_environment_only(api, monkeypatch):
    monkeypatch.delenv(cli.API_KEY_ENV)
    code, _, err = run("pull", "f1", "-o", "form.json")
    assert code == 1 and cli.API_KEY_ENV in err
    with pytest.raises(SystemExit):
        run("--api-key", KEY, "pull", "f1", "-o", "form.json")


def test_submit_and_update_a_submission(api, tmp_path):
    (tmp_path / "answers.json").write_text(json.dumps({"answers": {"name": "Ada"}}))
    # consent is asserted on the command line, never from the file
    code, _, err = run("submit", "f1", "answers.json")
    assert code == 1 and "consent_required" in err
    code, out, _ = run("submit", "f1", "answers.json", "--consent")
    assert code == 0 and "response r1" in out
    (tmp_path / "more.yaml").write_text(yaml.safe_dump({"answers": {"name": "Ada L."}}))
    code, out, _ = run("update-submission", "f1", "r1", "more.yaml")
    assert code == 0 and "response r1" in out
    assert api.submissions["r1"] == {"name": "Ada L."}


def test_a_submission_file_takes_answers_and_hidden_fields_only(api, tmp_path):
    (tmp_path / "bad.json").write_text(
        json.dumps({"answers": {}, "consent": True, "dataOwnerIdentifier": "x"})
    )
    code, _, err = run("submit", "f1", "bad.json", "--consent")
    assert code == 1 and "consent" in err and "dataOwnerIdentifier" in err
    (tmp_path / "list.json").write_text("[]")
    assert run("submit", "f1", "list.json")[0] == 1


def test_submit_names_the_optional_consent_items(api, tmp_path):
    (tmp_path / "answers.json").write_text(json.dumps({"answers": {"name": "Ada"}}))
    code, _, _ = run(
        "submit", "f1", "answers.json", "--consent",
        "--consent-item", "newsletter", "--consent-item", "research",
    )
    assert code == 0
    assert api.consent_items == ["newsletter", "research"]
    run("submit", "f1", "answers.json", "--consent")
    assert api.consent_items is None
