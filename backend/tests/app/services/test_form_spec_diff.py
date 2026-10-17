"""The structured diff of two spec documents (pure)."""

import copy

from backend.app.services.form_spec.diff import spec_diff


def _doc():
    return {
        "specVersion": "1",
        "title": "Form",
        "pages": [
            {
                "id": "p1",
                "fields": [
                    {"id": "a", "type": "short_text", "title": "A"},
                    {"id": "b", "type": "short_text", "title": "B"},
                    {"id": "c", "type": "short_text", "title": "C"},
                    {"id": "d", "type": "short_text", "title": "D"},
                ],
            },
            {
                "id": "p2",
                "fields": [
                    {
                        "id": "g",
                        "type": "group",
                        "title": "G",
                        "repeat": {"minItems": 1},
                        "fields": [{"id": "g1", "type": "short_text", "title": "G1"}],
                    }
                ],
            },
        ],
    }


def test_no_change():
    diff = spec_diff(_doc(), _doc())
    assert diff["changed"] is False
    assert diff["form"] == []
    for part in ("pages", "fields"):
        assert all(diff[part][kind] == [] for kind in diff[part])


def test_an_insertion_does_not_move_the_fields_after_it():
    after = _doc()
    after["pages"][0]["fields"].insert(
        0, {"id": "new", "type": "email", "title": "New"}
    )
    diff = spec_diff(_doc(), after)
    assert diff["fields"]["added"] == [{"id": "new", "path": "/pages/0/fields/0"}]
    assert diff["fields"]["moved"] == [] and diff["fields"]["changed"] == []


def test_moves_within_a_page_and_across_pages():
    after = _doc()
    fields = after["pages"][0]["fields"]
    fields.append(fields.pop(0))  # a to the end of p1
    moved_b = fields.pop(0)  # b to p2
    after["pages"][1]["fields"].append(moved_b)
    diff = spec_diff(_doc(), after)
    assert {m["id"] for m in diff["fields"]["moved"]} == {"a", "b"}
    b = next(m for m in diff["fields"]["moved"] if m["id"] == "b")
    assert (b["from"], b["to"]) == ("/pages/0/fields/1", "/pages/1/fields/1")


def test_removed_and_changed_with_group_children():
    after = _doc()
    del after["pages"][0]["fields"][2]
    group = after["pages"][1]["fields"][0]
    group["repeat"]["minItems"] = 2
    group["fields"][0]["title"] = "Child"
    after["title"] = "Renamed"
    del after["pages"][1]
    after["pages"].append(copy.deepcopy(_doc()["pages"][1]))
    after["pages"][1]["fields"][0]["fields"][0]["title"] = "Child"
    diff = spec_diff(_doc(), after)
    assert diff["fields"]["removed"] == [{"id": "c", "path": "/pages/0/fields/2"}]
    changed = {c["id"]: c["changes"] for c in diff["fields"]["changed"]}
    assert changed == {
        "g1": [
            {
                "path": "/pages/1/fields/0/fields/0/title",
                "before": "G1",
                "after": "Child",
            }
        ]
    }
    assert diff["form"] == [{"path": "/title", "before": "Form", "after": "Renamed"}]


def test_page_level_changes_and_an_object_that_appears():
    after = _doc()
    after["pages"][1]["jumps"] = [{"target": "__SUBMIT__"}]
    after["pages"][0]["sectionTitle"] = "Intro"
    after["trust"] = {"purpose": "Why"}
    diff = spec_diff(_doc(), after)
    changes = {c["id"]: c["changes"] for c in diff["pages"]["changed"]}
    assert changes["p1"] == [
        {"path": "/pages/0/sectionTitle", "before": None, "after": "Intro"}
    ]
    assert changes["p2"][0]["path"] == "/pages/1/jumps"
    assert diff["form"] == [{"path": "/trust/purpose", "before": None, "after": "Why"}]
