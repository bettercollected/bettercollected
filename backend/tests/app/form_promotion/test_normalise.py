"""The normalising step of a promotion, as a table: a document in, a document and
a report out. Pure: nothing here reads a database."""

import copy

from backend.app.services.form_promotion.normalise import (
    PRIVACY_KEYS,
    normalise,
    option_list_ids,
)
from backend.app.services.form_promotion.service import (
    counts_of,
    retention_shortened,
    spec_hash,
)

GOOD = "https://images.unsplash.com/photo-voorbeeld"
BAD = "https://beelden.voorbeeld.example/a.png"


def keep_unsplash(url):
    return url if url.startswith("https://images.unsplash.com/") else None


def runs(pattern):
    return not pattern.startswith("(?=")


def run(document, **options):
    options.setdefault("image_rule", keep_unsplash)
    options.setdefault("pattern_ok", runs)
    return normalise(document, **options)


def question(ident="q", **extra):
    return {"id": ident, "type": "short_text", "title": "Vraag", **extra}


def doc(*questions, **top):
    return {
        "specVersion": "1",
        "pages": [{"id": "p", "fields": list(questions)}],
        **top,
    }


def test_the_input_is_not_changed():
    source = doc(question(shareAsChoices=True, library={"sectionId": "s"}))
    before = copy.deepcopy(source)
    run(source)
    assert source == before


def test_images_that_are_not_first_party_are_dropped_everywhere_and_counted():
    source = doc(
        question("a", imageUrl=BAD),
        question("b", imageUrl=GOOD),
        welcomePage={"title": "Welkom", "imageUrl": BAD},
        endings=[{"id": "e", "title": "Klaar", "imageUrl": BAD}],
        theme={"background": {"imageUrl": BAD}},
    )
    source["pages"][0]["imageUrl"] = BAD
    result, report = run(source)
    assert report.images_dropped == 5
    assert "imageUrl" not in result["pages"][0]
    assert "imageUrl" not in result["pages"][0]["fields"][0]
    assert result["pages"][0]["fields"][1]["imageUrl"] == GOOD
    assert "imageUrl" not in result["welcomePage"]
    assert report.counts()["imagesDropped"] == 5


def test_a_first_party_address_is_kept_in_the_spelling_the_rule_gives():
    source = doc(question(imageUrl="https://images.unsplash.com/photo-oud"))
    result, report = run(
        source, image_rule=lambda url: "https://images.unsplash.com/photo-nieuw"
    )
    assert result["pages"][0]["fields"][0]["imageUrl"].endswith("photo-nieuw")
    assert report.images_dropped == 0


def test_a_pattern_the_server_cannot_run_is_dropped_and_the_question_named():
    source = doc(
        question("goed", validations={"pattern": "^a$", "required": True}),
        question("fout", validations={"pattern": "(?=x)y"}),
    )
    result, report = run(source)
    fields = result["pages"][0]["fields"]
    assert fields[0]["validations"] == {"pattern": "^a$", "required": True}
    assert "pattern" not in fields[1]["validations"]
    assert report.patterns_dropped == ["fout"]


def test_option_lists_are_matched_by_the_map_and_the_rest_dropped():
    source = doc(
        question("een", type="dropdown", optionSource={"kind": "list", "listId": "L1"}),
        question("twee", type="dropdown", optionSource={"kind": "list", "listId": "L2"}),
    )
    assert option_list_ids(source) == ["L1", "L2"]
    result, report = run(source, list_map={"L1": "T1"})
    fields = result["pages"][0]["fields"]
    assert fields[0]["optionSource"] == {"kind": "list", "listId": "T1"}
    assert "optionSource" not in fields[1]
    assert report.lists_remapped == ["een"]
    assert report.lists_dropped == ["twee"]


def test_options_from_another_forms_answers_are_always_dropped():
    source = doc(
        question(
            "wie",
            type="multiple_choice",
            optionSource={"kind": "form_answers", "formId": "F", "questionId": "naam"},
        )
    )
    # even when a map has an entry that looks like a match
    result, report = run(source, list_map={"F": "G"})
    assert "optionSource" not in result["pages"][0]["fields"][0]
    assert report.answer_sources_dropped == ["wie"]


def test_sharing_answers_as_choices_goes_off_and_library_markers_go():
    source = doc(
        question("a", shareAsChoices=True),
        question("b", library={"sectionId": "s", "revision": 1}),
        question("c", shareAsChoices=False),
    )
    result, report = run(source)
    for item in result["pages"][0]["fields"]:
        assert "shareAsChoices" not in item and "library" not in item
    assert report.share_as_choices_off == ["a"]
    assert report.library_markers_dropped == 1


def test_a_group_childs_question_level_rules_apply_too():
    source = doc(
        {
            "id": "groep",
            "type": "group",
            "title": "Groep",
            "fields": [question("kind", validations={"pattern": "(?=x)y"})],
        }
    )
    _, report = run(source)
    assert report.patterns_dropped == ["kind"]


def test_the_logo_file_is_not_carried_but_its_settings_are():
    source = doc(logo={"url": "https://opslag.voorbeeld.example/l.png", "alt": "Logo"})
    result, report = run(source)
    assert result["logo"] == {"alt": "Logo"}
    assert report.logo_file_not_copied is True


def test_a_new_target_takes_the_data_protection_settings_an_existing_one_keeps_its_own():
    trust = {
        "purpose": "x",
        "retentionText": "y",
        "privacyPolicyUrl": "https://p.voorbeeld.example/",
        "retention": {"type": "days", "value": 5},
        "requireVerifiedIdentity": True,
        "allowEditingResponse": True,
        "showSubmissionNumber": True,
    }
    source = doc(question(), trust=copy.deepcopy(trust))
    new, report = run(source, keep_target_privacy=False)
    assert new["trust"] == trust and report.trust_kept == []

    kept, report = run(source, keep_target_privacy=True)
    # only what is not data protection is sent
    assert kept["trust"] == {"showSubmissionNumber": True}
    assert set(report.trust_kept) == set(PRIVACY_KEYS)

    only, _ = run(doc(question(), trust={"purpose": "x"}), keep_target_privacy=True)
    assert "trust" not in only


def test_the_report_holds_ids_and_counts_never_an_address_or_a_text():
    source = doc(
        question("a", title="Geheime titel", imageUrl=BAD, shareAsChoices=True),
        question("b", validations={"pattern": "(?=x)y"}),
        question("c", type="dropdown", optionSource={"kind": "list", "listId": "L9"}),
    )
    _, report = run(source)
    shown = str(report.to_dict()) + str(report.counts())
    assert "voorbeeld" not in shown and "Geheime" not in shown and "L9" not in shown
    assert report.counts() == {
        "imagesDropped": 1,
        "patternsDropped": 1,
        "listsNotFound": 1,
        "shareAsChoicesOff": 1,
    }


def test_the_counts_of_a_document_and_its_hash():
    source = doc(
        question("a"),
        {"id": "g", "type": "group", "title": "G", "fields": [question("k")]},
    )
    assert counts_of(source) == {"pages": 1, "questions": 3}
    assert spec_hash({"a": 1, "b": 2}) == spec_hash({"b": 2, "a": 1})
    assert spec_hash({"a": 1}) != spec_hash({"a": 2})


def test_when_a_retention_shortens():
    days = lambda n: {"type": "days", "value": n}  # noqa: E731
    assert retention_shortened(days(90), days(30)) is True
    assert retention_shortened(days(30), days(90)) is False
    assert retention_shortened(days(30), {"type": "forever"}) is False
    assert retention_shortened({"type": "forever"}, days(30)) is True
    assert retention_shortened(days(30), None) is True
    # nothing was kept before: nothing can be shortened
    assert retention_shortened(None, days(1)) is False
    # days and an end date do not compare: warn
    assert retention_shortened(days(30), {"type": "date", "value": "2031-01-01"}) is True
