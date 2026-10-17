"""The form quality checker (services/ai/quality.py) on hand-built forms:
the checks the golden replies cannot reach (logic, internal fields, flat
forms, stored image hosts) and the scoring."""

import copy

from common.models.standard_form import StandardForm

from backend.app.services.ai.quality import (
    ERROR,
    QualityOptions,
    WARNING,
    check_form_quality,
    detect_language,
)

LEAFLET = {
    "title": "Leaflet",
    "primary": "#1A1A1A",
    "secondary": "#0B3D91",
    "tertiary": "#6B7A99",
    "accent": "#FFFFFF",
    "style": "leaflet",
}
UNSPLASH = "https://images.unsplash.com/photo-1?w=800"


def _choices(*labels):
    return [{"id": f"c{i}", "label": label, "value": label} for i, label in enumerate(labels)]


def _form(**overrides) -> dict:
    form = {
        "title": "Garden sign-up",
        "builder_version": "v2",
        "theme": dict(LEAFLET),
        "fields": [
            {
                "id": "p1",
                "type": "slide",
                "index": 0,
                "properties": {
                    "section_title": "About you",
                    "fields": [
                        {"id": "q1", "type": "short_text", "title": "What is your name?"},
                        {
                            "id": "q2",
                            "type": "multiple_choice",
                            "title": "Which plot size would you like?",
                            "properties": {"choices": _choices("Small", "Large")},
                        },
                    ],
                },
            },
            {
                "id": "p2",
                "type": "slide",
                "index": 1,
                "properties": {
                    "section_title": "Your plot",
                    "fields": [
                        {"id": "q3", "type": "yes_no", "title": "Do you have tools?"},
                        {"id": "q4", "type": "long_text", "title": "What will you grow?"},
                    ],
                },
            },
        ],
    }
    form.update(overrides)
    return form


def _codes(form, **options):
    return check_form_quality(form, QualityOptions(**options)).codes


def test_ai_quality_a_clean_form_scores_full_marks():
    report = check_form_quality(StandardForm.model_validate(_form()))
    assert report.findings == []
    assert report.score == 100
    assert report.passed
    assert report.as_dict() == {"score": 100, "passed": True, "findings": []}


def test_ai_quality_works_on_a_dict_as_on_the_model():
    form = _form()
    form["fields"][0]["properties"]["fields"].append(
        {"id": "q5", "type": "email", "title": "Your email?"}
    )
    assert _codes(form) == _codes(StandardForm.model_validate(form)) == [
        "missing_why_we_ask"
    ]


def test_ai_quality_dangling_visibility_rule_and_jump():
    form = _form()
    page1, page2 = form["fields"]
    page2["properties"]["fields"][0]["properties"] = {
        "logic": {
            "action": "SHOW",
            "conditions": [{"fieldId": "gone", "comparison": "IS_EQUAL", "value": "x"}],
        }
    }
    page1["properties"]["jumps"] = [
        {
            "operator": "AND",
            "target": "no-such-page",
            "conditions": [{"fieldId": "q2", "comparison": "IS_EQUAL", "value": "Small"}],
        },
        {"operator": "AND", "target": "__SUBMIT__", "conditions": []},
    ]
    report = check_form_quality(StandardForm.model_validate(form))
    dangling = [f for f in report.findings if f.code == "dangling_logic_reference"]
    assert [f.where for f in dangling] == [("p1", "no-such-page"), ("q3", "gone")]
    assert all(f.severity == ERROR for f in dangling)


def test_ai_quality_logic_on_existing_ids_is_fine():
    form = _form()
    form["fields"][1]["properties"]["fields"][0]["properties"] = {
        "logic": {
            "action": "SHOW",
            "conditions": [{"fieldId": "q2", "comparison": "IS_EQUAL", "value": "Large"}],
        }
    }
    form["fields"][0]["properties"]["jumps"] = [
        {"target": "p2", "conditions": [{"fieldId": "q1", "comparison": "IS_NOT_EMPTY"}]}
    ]
    assert _codes(form) == []


def test_ai_quality_stored_images_must_come_from_allowed_hosts():
    form = _form(cover_image="https://cdn.example.org/cover.png")
    form["theme"]["background"] = {"type": "image", "imageUrl": UNSPLASH}
    form["fields"][0]["image_url"] = "https://tracker.example.com/p.gif"
    report = check_form_quality(form)
    assert report.codes == ["external_image", "external_image"]
    assert sorted(f.where for f in report.findings) == [("cover_image",), ("p1",)]


def test_ai_quality_page_length_limit_is_configurable_and_ignores_statements():
    form = _form()
    page = form["fields"][0]["properties"]["fields"]
    page.append({"id": "t1", "type": "text", "title": "Some words"})
    page.append({"id": "i1", "type": "short_text", "title": "Office ref", "internal": True})
    assert _codes(form, max_questions_per_page=2) == []
    page.append({"id": "q9", "type": "number", "title": "How many plots?"})
    assert _codes(form, max_questions_per_page=2) == ["too_many_questions_on_page"]


def test_ai_quality_section_titles_only_matter_on_multi_page_leaflet_forms():
    form = _form()
    form["fields"][1]["properties"]["section_title"] = None
    assert _codes(form) == ["missing_section_titles"]
    finding = check_form_quality(form).findings[0]
    assert finding.where == ("2",) and finding.severity == WARNING

    classic = copy.deepcopy(form)
    classic["theme"] = dict(LEAFLET, title="Default", style=None)
    assert _codes(classic, theme_requested=True) == []

    single = copy.deepcopy(form)
    single["fields"] = single["fields"][1:]
    assert _codes(single) == []


def test_ai_quality_theme_default_and_requests():
    other = _form(theme=dict(LEAFLET, title="Green", style=None))
    assert _codes(other) == ["theme_not_default"]
    assert _codes(other, theme_requested=True) == []
    assert _codes(_form(), theme_requested=True) == ["theme_request_ignored"]


def test_ai_quality_flat_form_is_one_page():
    flat = {
        "title": "Flat",
        "theme": dict(LEAFLET),
        "fields": [
            {"id": "a", "type": "short_text", "title": "Name?"},
            {"id": "b", "type": "short_text", "title": "Name?"},
        ],
    }
    assert _codes(flat) == ["duplicate_question"]
    assert _codes(flat, max_questions_per_page=1) == [
        "duplicate_question",
        "too_many_questions_on_page",
    ]


def test_ai_quality_internal_fields_are_not_respondent_questions():
    form = _form()
    form["fields"][0]["properties"]["fields"].append(
        {"id": "i1", "type": "short_text", "title": "What is your name?", "internal": True}
    )
    assert _codes(form) == []


def test_ai_quality_no_title_and_no_questions():
    report = check_form_quality({"title": "  ", "theme": dict(LEAFLET), "fields": []})
    assert report.codes == ["missing_title", "no_questions"]
    assert report.score == 60
    assert not report.passed


def test_ai_quality_score_counts_errors_and_warnings_and_floors_at_zero():
    form = _form()
    form["fields"][1]["properties"]["section_title"] = ""
    form["theme"] = dict(LEAFLET, title="Red", style=None)
    # one warning (theme); section titles do not apply to a non-Leaflet form
    assert check_form_quality(form).score == 95
    empty = {"title": "", "fields": [], "cover_image": "https://x.example/a.png"}
    report = check_form_quality(empty, QualityOptions(theme_requested=True))
    assert report.score == 40
    many = _form()
    many["fields"][0]["properties"]["fields"] += [
        {"id": f"e{i}", "type": "email", "title": f"Email {i}?"} for i in range(8)
    ]
    assert check_form_quality(many).score == 0


def test_ai_quality_is_deterministic():
    form = StandardForm.model_validate(_form(cover_image="https://x.example/a.png"))
    first = check_form_quality(form, QualityOptions(language="nl")).as_dict()
    for _ in range(3):
        assert check_form_quality(form, QualityOptions(language="nl")).as_dict() == first


def test_ai_quality_language_detection():
    assert detect_language("What is your name and where do you live?") == "en"
    assert detect_language("Wat is je naam en waar woon je?") == "nl"
    assert detect_language("Naam") is None
    assert (
        detect_language("What is your name and where do you live? Wat is je naam en waar woon je?")
        == "mixed"
    )
    assert _codes(_form(), language="en") == []
    assert _codes(_form(), language="nl") == ["wrong_language"]


def test_ai_quality_request_caps_the_number_of_questions():
    assert _codes(_form(), max_questions=4) == []
    report = check_form_quality(_form(), QualityOptions(max_questions=3))
    assert report.codes == ["too_many_questions"]
    assert report.findings[0].severity == ERROR


def test_ai_quality_request_implies_question_types():
    assert _codes(_form(), expected_types=frozenset({"yes_no", "long_text"})) == []
    report = check_form_quality(
        _form(), QualityOptions(expected_types=frozenset({"email", "date", "yes_no"}))
    )
    assert report.codes == ["missing_field_type", "missing_field_type"]
    assert [f.where for f in report.findings] == [("date",), ("email",)]


def test_ai_quality_yes_no_fixed_choices_do_not_count_as_english():
    form = {
        "title": "Aanmelding",
        "theme": dict(LEAFLET),
        "fields": [
            {
                "id": "p1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "a", "type": "yes_no", "title": "Kom je naar de bijeenkomst?",
                         "properties": {"choices": _choices("Yes", "No")}},
                        {"id": "b", "type": "long_text", "title": "Wat wil je met ons delen over de wijk?"},
                    ]
                },
            }
        ],
    }
    assert _codes(form, language="nl") == []
