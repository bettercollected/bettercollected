"""update_form_settings semantics live in one place (apply_settings_ops),
used by the save and the dry run alike."""

from common.models.standard_form import StandardForm

from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.services.ai.ops import apply_form_ops, apply_settings_ops, parse_ops
from backend.app.services.form_spec.service import settings_after_ops

OPS = parse_ops(
    [
        {
            "op": "update_form_settings",
            "patch": {"purpose": "  To plan.  ", "retentionText": ""},
        },
        {"op": "update_form_settings", "patch": {"privacyPolicyUrl": "not a url"}},
        {
            "op": "update_form_settings",
            "patch": {"showSubmissionNumber": True, "allowEditingResponse": False},
        },
    ]
)


def _results():
    _, results = apply_form_ops(StandardForm(fields=[]), OPS)
    return results


def test_apply_settings_ops_trims_clears_and_skips_failed_ops():
    settings = WorkspaceFormSettings(
        retention_text="Old", privacy_policy_url="https://a.example"
    )
    results = _results()
    assert [r.ok for r in results] == [True, False, True]
    assert apply_settings_ops(settings, OPS, results) is True
    assert settings.purpose == "To plan."
    assert settings.retention_text is None
    assert settings.privacy_policy_url == "https://a.example"
    assert (settings.show_submission_number, settings.allow_editing_response) == (
        True,
        False,
    )


def test_nothing_to_apply():
    settings = WorkspaceFormSettings(purpose="Kept")
    assert apply_settings_ops(settings, OPS[1:2], _results()[1:2]) is False
    assert settings.purpose == "Kept"


def test_the_dry_run_uses_a_copy_with_the_same_result():
    stored = WorkspaceFormSettings(retention_text="Old")
    preview = settings_after_ops(stored, OPS, _results())
    assert stored.retention_text == "Old" and stored.purpose is None
    saved = stored.model_copy(deep=True)
    apply_settings_ops(saved, OPS, _results())
    assert preview == saved
    assert settings_after_ops(None, OPS, _results()) is None
