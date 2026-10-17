"""Golden AI replies through the real pipeline and the quality checks.

Each file in tests/fixtures/ai_evals/ (except prompts.json) is a recorded or
synthetic model reply with the findings it must produce. An outline reply
goes through ``parse_outline``, the outline compiler and the ops engine
(the product's generation), an earlier whole-form reply through
``parse_generated_form`` and the form converter, a chat reply through the
chat turn's reply model and the ops engine; then
``check_form_quality`` scores the form. No provider is called.

When a prompt or the checker changes on purpose, update the expected
findings here; an unexpected change is what this suite is for.
"""

import json
from pathlib import Path

import pytest

from backend.app.services.ai import eval_pipeline
from backend.app.services.ai.structured import InvalidReply, extract_json_object

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ai_evals"
CASE_FILES = sorted(p for p in FIXTURES.glob("*.json") if p.name != "prompts.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(case: dict):
    if case["kind"] == eval_pipeline.CHAT:
        form, results = eval_pipeline.chat_reply_to_form(
            case["base_form"], case["reply"]
        )
        return eval_pipeline.score(form, case), results
    if case["kind"] == eval_pipeline.OUTLINE:
        _, form = eval_pipeline.outline_reply_to_form(case["reply"])
        return eval_pipeline.score(form, case), []
    raw, form = eval_pipeline.generation_reply_to_form(case["reply"])
    return eval_pipeline.score(form, case, raw=raw), []


def test_ai_eval_fixture_set_covers_both_languages_and_both_paths():
    cases = [_load(p) for p in CASE_FILES]
    assert len(cases) >= 20
    assert {c["language"] for c in cases} >= {"en", "nl"}
    assert {c["kind"] for c in cases} == {"generate", "chat", "outline"}
    outlines = [c for c in cases if c["kind"] == "outline"]
    assert {c["language"] for c in outlines} >= {"en", "nl"}
    assert any(not c["expected_findings"] for c in outlines), "no good outlines"
    assert any(not c["expected_findings"] for c in cases), "no good cases"
    assert sum(bool(c["expected_findings"]) for c in cases) >= 10, "few bad cases"
    for case, path in zip(cases, CASE_FILES):
        assert case["name"] == path.stem


@pytest.mark.parametrize("path", CASE_FILES, ids=[p.stem for p in CASE_FILES])
def test_ai_eval_fixture(path):
    case = _load(path)
    if case.get("expect_invalid"):
        with pytest.raises(InvalidReply):
            _run(case)
        return

    report, results = _run(case)

    assert report.codes == sorted(case["expected_findings"])
    assert report.passed == (
        not any(f.severity == "error" for f in report.findings)
    )
    if case["expected_findings"]:
        assert report.score < 100
    else:
        assert report.score == 100
    failed = [r for r in results if not r.ok]
    assert len(failed) == case.get("expected_failed_ops", 0)


@pytest.mark.parametrize("path", CASE_FILES, ids=[p.stem for p in CASE_FILES])
def test_ai_eval_findings_never_quote_the_form(path):
    """Reports are shared: findings name codes, ids and page numbers only."""
    case = _load(path)
    if case.get("expect_invalid"):
        return
    report, _ = _run(case)
    blob = json.dumps(report.as_dict(), ensure_ascii=False)
    reply = case["reply"]
    if isinstance(reply, str):  # a fenced reply
        reply = extract_json_object(reply)
    titles = set(_titles(reply)) | set(_titles(case.get("base_form")))
    assert titles
    for title in titles:
        assert title not in blob


def _titles(value):
    """Every title in a reply or form."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("title", "label") and isinstance(item, str):
                yield item
            else:
                yield from _titles(item)
    elif isinstance(value, list):
        for item in value:
            yield from _titles(item)
