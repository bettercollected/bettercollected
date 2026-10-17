"""The ``set_section_title`` op and where the AI learns about section titles
(pure logic: no database, no network)."""

import pytest
from common.models.standard_form import (
    SECTION_TITLE_MAX_LENGTH,
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
    ThankYouPageField,
    WelcomePageField,
)

from backend.app.container import container
from backend.app.mcp import server as mcp_server
from backend.app.services import (
    google_ai_provider,
    openai_compatible_provider,
    openai_provider,
)
from backend.app.services.ai.ops import (
    SetSectionTitleOp,
    apply_form_ops,
    parse_ops,
)
from backend.app.services.ai.prompt_builder import OPS_GUIDE, project_form
from backend.app.services.ai.review import build_review_system_prompt
from backend.app.services.form_generation_rules import SECTION_TITLE_RULES


def _page(page_id: str, index: int, title: str, section_title=None) -> StandardFormField:
    return StandardFormField(
        id=page_id,
        index=index,
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(
            section_title=section_title,
            fields=[
                StandardFormField(
                    id=f"{page_id}-q",
                    index=0,
                    type=StandardFormFieldType.SHORT_TEXT,
                    title=title,
                    properties=StandardFieldProperty(fields=[]),
                )
            ],
        ),
    )


@pytest.fixture()
def form() -> StandardForm:
    return StandardForm(
        builder_version="v2",
        form_id="form-1",
        title="Visit",
        welcome_page=WelcomePageField(title="Visit"),
        thankyou_page=[ThankYouPageField()],
        fields=[
            _page("page-1", 0, "Your name"),
            _page("page-2", 1, "When did you visit?", section_title="Old title"),
        ],
    )


def _section_titles(form: StandardForm):
    return [p.properties.section_title for p in form.fields]


def _apply(form, *raw_ops):
    return apply_form_ops(form, parse_ops(list(raw_ops)))


class TestSetSectionTitle:
    def test_sets_by_page_id(self, form):
        new_form, results = _apply(
            form, {"op": "set_section_title", "pageId": "page-1", "title": "About you"}
        )
        assert results[0].ok, results[0].message
        assert results[0].message == "Section title of page 1: 'About you'"
        assert _section_titles(new_form) == ["About you", "Old title"]
        # the original is untouched
        assert _section_titles(form) == [None, "Old title"]

    def test_sets_by_page_index(self, form):
        new_form, results = _apply(
            form,
            {"op": "set_section_title", "pageIndex": 1, "title": "About your visit"},
        )
        assert results[0].ok, results[0].message
        assert results[0].message == "Section title of page 2: 'About your visit'"
        assert _section_titles(new_form) == [None, "About your visit"]

    @pytest.mark.parametrize("cleared", [None, "", "   "])
    def test_null_or_empty_clears(self, form, cleared):
        new_form, results = _apply(
            form, {"op": "set_section_title", "pageId": "page-2", "title": cleared}
        )
        assert results[0].ok, results[0].message
        assert results[0].message.startswith("Cleared the section title of page 2")
        assert _section_titles(new_form) == [None, None]

    def test_plain_text_on_one_line(self, form):
        new_form, results = _apply(
            form,
            {"op": "set_section_title", "pageId": "page-1", "title": "  About\n  you \t"},
        )
        assert results[0].ok
        assert _section_titles(new_form)[0] == "About you"

    def test_length_is_capped(self, form):
        longest = "a" * SECTION_TITLE_MAX_LENGTH
        new_form, results = _apply(
            form,
            {"op": "set_section_title", "pageId": "page-1", "title": longest + "b"},
            {"op": "set_section_title", "pageId": "page-2", "title": longest},
        )
        assert not results[0].ok
        assert "at most 120 characters" in results[0].message
        # one long title fails alone; the next op still applies
        assert results[1].ok
        assert _section_titles(new_form) == [None, longest]

    def test_missing_page(self, form):
        _, results = _apply(
            form,
            {"op": "set_section_title", "pageId": "gone", "title": "X"},
            {"op": "set_section_title", "pageIndex": 2, "title": "X"},
            {"op": "set_section_title", "pageIndex": -1, "title": "X"},
        )
        assert [r.ok for r in results] == [False, False, False]
        assert "was not found" in results[0].message
        assert "2 question page(s)" in results[1].message

    @pytest.mark.parametrize(
        "page_id, page_name",
        [
            ("welcome", "welcome page"),
            ("welcome_page", "welcome page"),
            ("ending", "ending"),
            ("thankyou_page", "ending"),
            ("thank_you", "ending"),
        ],
    )
    def test_welcome_page_and_ending_are_refused(self, form, page_id, page_name):
        new_form, results = _apply(
            form, {"op": "set_section_title", "pageId": page_id, "title": "Hello"}
        )
        assert not results[0].ok
        assert f"the {page_name} has none" in results[0].message
        assert _section_titles(new_form) == [None, "Old title"]

    def test_a_question_id_is_not_a_page(self, form):
        _, results = _apply(
            form, {"op": "set_section_title", "pageId": "page-1-q", "title": "X"}
        )
        assert not results[0].ok
        assert "is a question, not a page" in results[0].message

    def test_needs_exactly_one_page_reference(self, form):
        _, results = _apply(
            form,
            {"op": "set_section_title", "title": "X"},
            {"op": "set_section_title", "pageId": "page-1", "pageIndex": 0, "title": "X"},
        )
        assert [r.ok for r in results] == [False, False]
        assert "pageId or a pageIndex" in results[0].message

    def test_needs_a_title_key(self, form):
        new_form, results = _apply(form, {"op": "set_section_title", "pageId": "page-2"})
        assert not results[0].ok
        assert '"title"' in results[0].message
        # a forgotten title never clears the stored one
        assert _section_titles(new_form) == [None, "Old title"]

    def test_follows_a_page_added_in_the_same_turn(self, form):
        new_form, results = _apply(
            form,
            {"op": "add_page", "index": 0},
            {"op": "set_section_title", "pageIndex": 0, "title": "Before you start"},
        )
        assert all(r.ok for r in results), results
        assert results[1].message == "Section title of page 1: 'Before you start'"
        assert _section_titles(new_form)[0] == "Before you start"

    def test_parses_as_a_typed_op(self):
        (op,) = parse_ops([{"op": "set_section_title", "pageId": "p", "title": "T"}])
        assert isinstance(op, SetSectionTitleOp)
        assert op.model_dump(by_alias=True)["pageId"] == "p"


class TestTheModelIsTold:
    def test_chat_and_review_prompts_describe_the_op(self, form):
        assert '"op":"set_section_title"' in OPS_GUIDE
        assert "B1" in OPS_GUIDE and "120 characters" in OPS_GUIDE
        review = build_review_system_prompt(project_form(form), None)
        assert "set_section_title" in review

    def test_the_snapshot_shows_section_titles(self, form):
        import json

        snapshot = json.loads(project_form(form))
        assert "sectionTitle" not in snapshot["pages"][0]
        assert snapshot["pages"][1]["sectionTitle"] == "Old title"

    def test_mcp_update_form_documents_the_op(self):
        assert "set_section_title" in (mcp_server.update_form.__doc__ or "")

    @pytest.mark.parametrize(
        "prompt",
        [
            openai_provider.SYSTEM_PROMPT,
            google_ai_provider.SYSTEM_PROMPT,
            openai_compatible_provider.GENERATION_SYSTEM_PROMPT,
        ],
    )
    def test_every_generator_may_set_section_titles(self, prompt):
        assert "sectionTitle?: string" in prompt
        assert SECTION_TITLE_RULES in prompt
        assert "optional" in SECTION_TITLE_RULES.lower()


class TestGeneratedSectionTitles:
    def _convert(self, *pages):
        return container.openai_service().convert_openai_form_to_standard_form(
            {"title": "Visit", "fields": list(pages)}
        )

    def test_generated_pages_keep_their_section_titles(self):
        form = self._convert(
            {"title": "Name", "type": "short_text", "sectionTitle": " About\nyou "},
            {
                "title": "Your visit",
                "type": "group",
                "sectionTitle": "About your visit",
                "properties": {
                    "fields": [
                        {"title": "When?", "type": "date"},
                        {"title": "Why?", "type": "long_text"},
                    ]
                },
            },
            {"title": "Comments", "type": "long_text"},
        )
        assert _section_titles(form) == ["About you", "About your visit", None]

    @pytest.mark.parametrize(
        "value", ["", "   ", "x" * (SECTION_TITLE_MAX_LENGTH + 1), 42, ["a"]]
    )
    def test_unusable_section_titles_are_left_out(self, value):
        form = self._convert({"title": "Name", "type": "short_text", "sectionTitle": value})
        assert _section_titles(form) == [None]
