"""What a column may be filled into, and how headers are matched."""

from backend.app.services.response_import.targets import (
    STATUS_IGNORED,
    STATUS_OK,
    STATUS_UNSUPPORTED,
    build_targets,
    group_key,
    split_group_key,
    suggest_mapping,
)


def form(fields, hidden=None, title="F"):
    return {
        "builder_version": "v2",
        "title": title,
        "hidden_fields": hidden or [],
        "fields": [{"id": "s1", "type": "slide", "index": 0, "properties": {"fields": fields}}],
    }


FIELDS = [
    {"id": "q1", "type": "short_text", "title": "Full name"},
    {"id": "q2", "type": "short_text", "title": "Full name"},
    {"id": "q3", "type": "file_upload", "title": "CV"},
    {"id": "q4", "type": "calculated", "title": "Total"},
    {"id": "q5", "type": "number", "title": "Age", "internal": True},
    {"id": "q6", "type": "matrix", "title": "Grid", "properties": {"fields": []}},
    {
        "id": "g1",
        "type": "group",
        "title": "Jobs",
        "properties": {
            "repeat": {"max_items": 2, "item_label": "Job", "export_layout": "columns"},
            "fields": [{"id": "e1", "type": "short_text", "title": "Employer"}],
        },
    },
    {
        "id": "g2",
        "type": "group",
        "title": "Kids",
        "properties": {
            "repeat": {"max_items": 9, "export_layout": "rows"},
            "fields": [{"id": "k1", "type": "short_text", "title": "Kid"}],
        },
    },
]


def by_key(targets):
    return {t.key: t for t in targets}


def test_targets_follow_the_exports_columns():
    targets = build_targets(form(FIELDS, hidden=["utm"]))
    keys = [t.key for t in targets]
    assert keys[0] == "responder" and keys[-3:] == ["response_id", "submitted_at", "hidden:utm"]
    found = by_key(targets)
    assert found["q:q1"].status == STATUS_OK
    assert found["q:q3"].status == STATUS_UNSUPPORTED
    assert found["q:q4"].status == STATUS_IGNORED and found["q:q4"].reason == "calculated_ignored"
    assert found["q:g2"].status == STATUS_IGNORED and found["q:g2"].reason == "group_rows_ignored"
    assert found["responder"].status == STATUS_IGNORED and found["response_id"].status == STATUS_IGNORED
    # staff-only questions import when staff can fill that type in
    assert found["internal:q5"].status == STATUS_OK
    assert "q:q6" not in found


def test_a_group_has_a_target_per_item_and_question():
    found = by_key(build_targets(form(FIELDS)))
    key = group_key("g1", 1, "e1")
    assert found[key].label == "Job 2 – Employer" and found[key].item == 1
    assert split_group_key(key) == ("g1", 1, "e1")
    assert split_group_key("q:g1") is None


def test_headers_match_by_the_exports_text_in_order_and_notes_say_what_is_left_out():
    targets = build_targets(form(FIELDS, hidden=["utm"]))
    headers = ["Responder ID", "full  NAME", "Full name", "CV", "Total", "Job 1 – Employer", "Job 2 - Employer", "Response ID", "Hidden: utm", "unknown", ""]
    mapping, notes = suggest_mapping(headers, targets)
    assert mapping == {
        "1": "q:q1",
        "2": "q:q2",
        "5": group_key("g1", 0, "e1"),
        "6": group_key("g1", 1, "e1"),
        "8": "hidden:utm",
    }
    assert {(n["column"], n["code"]) for n in notes} == {
        (0, "responder_ignored"),
        (3, "type_unsupported"),
        (4, "calculated_ignored"),
        (7, "response_id_ignored"),
    }


def test_a_question_id_matches_too_and_a_target_is_used_once():
    targets = build_targets(form(FIELDS))
    mapping, _ = suggest_mapping(["q1", "q:q1", "Age"], targets)
    assert mapping == {"0": "q:q1", "2": "internal:q5"} or mapping == {"0": "q:q1"}


def test_the_drafts_headers_are_accepted_for_a_question_retitled_since():
    published = form([{"id": "q1", "type": "short_text", "title": "Name"}])
    draft = form([{"id": "q1", "type": "short_text", "title": "Full name"}])
    mapping, _ = suggest_mapping(["Full name"], build_targets(published, draft))
    assert mapping == {"0": "q:q1"}
    # a question only the draft has is not offered
    draft["fields"][0]["properties"]["fields"].append({"id": "new", "type": "short_text", "title": "New"})
    assert "q:new" not in by_key(build_targets(published, draft))
