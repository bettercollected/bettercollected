import json

from smoke.__main__ import main
from tests.conftest import APP_PASSWORD, REFRESH_TOKEN


def test_an_incomplete_configuration_exits_2_with_a_report(
    tmp_path, monkeypatch, base_env, capsys
):
    for name in list(base_env) + ["SMOKE_IMAP_APP_PASSWORD", "GITHUB_STEP_SUMMARY"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in base_env.items():
        monkeypatch.setenv(name, value)
    # both mailbox sets: refused before anything runs
    monkeypatch.setenv("SMOKE_IMAP_APP_PASSWORD", APP_PASSWORD)
    monkeypatch.setenv("SMOKE_GMAIL_CLIENT_ID", "id.apps.googleusercontent.com")
    monkeypatch.setenv("SMOKE_GMAIL_CLIENT_SECRET", "GOCSPX-secret-value")
    monkeypatch.setenv("SMOKE_GMAIL_REFRESH_TOKEN", REFRESH_TOKEN)
    assert main(["--report-dir", str(tmp_path)]) == 2
    data = json.loads((tmp_path / "report.json").read_text())
    assert data["result"] == "fail"
    assert "both mailbox sets" in data["checks"][0]["notes"][0]
    printed = capsys.readouterr()
    for text in (printed.out, printed.err, (tmp_path / "summary.md").read_text()):
        assert APP_PASSWORD not in text and REFRESH_TOKEN not in text


def test_devstack_prepares_local_stacks_only(tmp_path):
    from smoke.devstack import main as devstack

    env_file = tmp_path / "x.env"
    args = ["--api", "https://admin.example.com/api/v1"]
    args += ["--mailpit", "http://localhost:8025", "--origin", "https://admin.example.com"]
    assert devstack(args + ["--env-file", str(env_file)]) == 2
    assert not env_file.exists()
