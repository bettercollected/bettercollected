"""Normalising a document for another workspace, and the words of a diff."""

import copy
import io

from bettercollected import cli, promote

UNSPLASH = "https://images.unsplash.com/photo-1?w=800"
OTHER_STORAGE = "https://s3.staging.example/bucket/media_library/ws/a.png"


def document():
    return {
        "specVersion": "1",
        "title": "Event sign-up",
        "welcomePage": {"title": "Hi", "imageUrl": OTHER_STORAGE},
        "theme": {"background": {"imageUrl": UNSPLASH}},
        "pages": [
            {
                "id": "p1",
                "imageUrl": OTHER_STORAGE,
                "fields": [
                    {
                        "id": "city",
                        "type": "dropdown",
                        "title": "City",
                        "optionSource": {"kind": "list", "listId": "L-stg"},
                        "library": {"sectionId": "s", "version": 1, "key": "k"},
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
                    {
                        "id": "code",
                        "type": "short_text",
                        "title": "Code",
                        "shareAsChoices": True,
                        "imageUrl": OTHER_STORAGE,
                        "validations": {"pattern": "^(?=a)b$"},
                    },
                    {
                        "id": "group",
                        "type": "group",
                        "title": "Group",
                        "fields": [
                            {
                                "id": "inner",
                                "type": "short_text",
                                "title": "Inner",
                                "validations": {"pattern": "^[0-9]+$"},
                                "library": {"sectionId": "s"},
                            }
                        ],
                    },
                ],
            }
        ],
        "logo": {"url": "https://x.example/logo.png", "position": "left"},
        "trust": {
            "purpose": "Staging purpose",
            "retention": {"type": "days", "value": 1},
            "privacyPolicyUrl": "https://staging.example/privacy",
            "allowSaveDraft": True,
        },
    }


def find(fields, field_id):
    for item in fields or []:
        if item["id"] == field_id:
            return item
        inner = find(item.get("fields"), field_id)
        if inner:
            return inner
    return None


def question(doc, field_id):
    return find(doc["pages"][0]["fields"], field_id)


def test_normalise_does_not_change_its_input():
    source = document()
    snapshot = copy.deepcopy(source)
    promote.normalise(source)
    assert source == snapshot


def test_other_instance_drops_foreign_images_and_keeps_unsplash_photos():
    result, report = promote.normalise(document())
    assert "imageUrl" not in result["welcomePage"]
    assert "imageUrl" not in result["pages"][0]
    assert "imageUrl" not in question(result, "code")
    assert result["theme"]["background"]["imageUrl"] == UNSPLASH
    assert sorted(report.images_dropped) == [
        "/pages/0/fields/2/imageUrl",
        "/pages/0/imageUrl",
        "/welcomePage/imageUrl",
    ]


def test_same_instance_shares_storage_so_images_stay():
    result, report = promote.normalise(document(), shared_storage=True)
    assert result["welcomePage"]["imageUrl"] == OTHER_STORAGE
    assert report.images_dropped == []


def test_lists_are_matched_through_the_map_and_dropped_without_one():
    mapped, report = promote.normalise(document(), list_map={"L-stg": "L-prod"})
    assert question(mapped, "city")["optionSource"] == {
        "kind": "list",
        "listId": "L-prod",
    }
    assert report.lists_remapped == ["city"] and report.lists_dropped == []

    dropped, report = promote.normalise(document(), list_map={"other": "x"})
    assert "optionSource" not in question(dropped, "city")
    assert report.lists_dropped == ["city"]


def test_options_from_another_forms_answers_are_always_dropped():
    # even when a list map exists: the target's staff decide that themselves
    result, report = promote.normalise(document(), list_map={"F": "x"})
    assert "optionSource" not in question(result, "who")
    assert report.answer_sources_dropped == ["who"]


def test_patterns_re2_cannot_run_are_dropped_and_others_kept():
    result, report = promote.normalise(document())
    assert "pattern" not in question(result, "code")["validations"]
    assert question(result, "inner")["validations"]["pattern"] == "^[0-9]+$"
    assert report.patterns_dropped == ["code"]
    for bad in ("(a)\\1", "(?<=a)b", "(?<!a)b", "(?!a)b", "x" * 201):
        assert not promote._usable_pattern(bad)
    assert promote._usable_pattern("^[a-z]{2,4}$")


def test_share_as_choices_and_library_markers_go_in_groups_too():
    result, report = promote.normalise(document())
    assert "shareAsChoices" not in question(result, "code")
    assert "library" not in question(result, "city")
    assert "library" not in question(result, "inner")
    assert report.share_as_choices_off == ["code"]
    assert report.library_markers_dropped == 2


def test_the_logo_file_is_not_carried_but_its_settings_are():
    result, report = promote.normalise(document())
    assert result["logo"] == {"position": "left"}
    assert report.logo_file_not_copied


def test_a_new_target_takes_the_trust_settings():
    result, report = promote.normalise(document())
    assert result["trust"]["purpose"] == "Staging purpose"
    assert report.trust_kept == []


def test_an_existing_target_keeps_its_own_data_protection_settings():
    result, report = promote.normalise(document(), keep_target_privacy=True)
    # left out, so the writer keeps what the target stores
    assert result["trust"] == {"allowSaveDraft": True}
    assert report.trust_kept == ["purpose", "privacyPolicyUrl", "retention"]

    only, _ = promote.normalise(
        {"specVersion": "1", "trust": {"purpose": "x"}, "pages": []},
        keep_target_privacy=True,
    )
    assert "trust" not in only


def test_a_clean_document_reports_nothing_adjusted():
    plain = {"specVersion": "1", "title": "T", "pages": [{"id": "p", "fields": []}]}
    result, report = promote.normalise(plain)
    assert result == plain and not report.adjusted


def test_same_instance_compares_scheme_host_and_port():
    assert promote.same_instance("https://a.example/", "https://A.example:443/x")
    assert promote.same_instance("https://a.example/x", "https://A.example/y")
    assert not promote.same_instance("https://a.example", "https://b.example")
    assert not promote.same_instance("https://a.example", "http://a.example")


def test_retention_shortened():
    def days(n):
        return {"type": "days", "value": n}

    assert promote.retention_shortened(days(365), days(30))
    assert not promote.retention_shortened(days(30), days(365))
    assert not promote.retention_shortened(days(30), {"type": "forever"})
    assert promote.retention_shortened({"type": "forever"}, days(30))
    assert promote.retention_shortened(days(30), None)
    assert not promote.retention_shortened(None, days(30))
    assert promote.retention_shortened(
        days(30), {"type": "date", "value": "2030-01-01"}
    )


def test_the_report_names_counts_and_question_ids_never_addresses():
    _, report = promote.normalise(document())
    out = io.StringIO()
    promote.render_report(report, out)
    text = out.getvalue()
    assert "3 image(s) dropped" in text
    assert "who" in text and "code" in text
    assert "responses (answers are never copied)" in text
    assert "Never copied:" in text
    assert OTHER_STORAGE not in text and "staging.example" not in text
    assert "logo file" in text


def test_the_diff_is_printed_in_words():
    diff = {
        "form": [{"path": "/title", "before": "A", "after": "B"}],
        "pages": {
            "added": [{"id": "p2", "path": "/pages/1"}],
            "removed": [],
            "moved": [],
            "changed": [],
        },
        "fields": {
            "added": [{"id": "age", "path": "/pages/0/fields/1"}],
            "removed": [{"id": "old", "path": "/pages/0/fields/2"}],
            "moved": [
                {
                    "id": "name",
                    "from": "/pages/0/fields/0",
                    "to": "/pages/1/fields/0",
                }
            ],
            "changed": [
                {
                    "id": "name",
                    "changes": [
                        {"path": "/fields/name/title", "before": "N", "after": "M"}
                    ],
                }
            ],
        },
        "changed": True,
    }
    out = io.StringIO()
    cli._print_diff(diff, out)
    assert out.getvalue().splitlines() == [
        '~ /title: "A" -> "B"',
        "+ page p2 at /pages/1",
        "+ field age at /pages/0/fields/1",
        "- field old (was /pages/0/fields/2)",
        "> field name moved /pages/0/fields/0 -> /pages/1/fields/0",
        '~ /fields/name/title: "N" -> "M"',
    ]
