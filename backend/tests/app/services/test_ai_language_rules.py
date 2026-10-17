"""The language rule reaches every generation prompt and the chat prompt:
one language for the whole form, the request's (or the form's) unless
another is asked for, with the organization's as the default."""

from backend.app.services.ai.prompt_builder import OPS_GUIDE, build_chat_system_prompt
from backend.app.services.ai.outline_service import (
    GAP_FILL_SYSTEM_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
)
from backend.app.services.form_generation_rules import LANGUAGE_RULES


def test_the_outline_prompt_has_the_language_rule():
    assert LANGUAGE_RULES in OUTLINE_SYSTEM_PROMPT
    # gap filling writes in the outline's language
    assert "outline's language" in GAP_FILL_SYSTEM_PROMPT


def test_the_generation_rule_covers_all_text_and_the_defaults():
    rule = " ".join(LANGUAGE_RULES.split())
    for text in (
        "Write the whole form in one language",
        "questions",
        "choices",
        "section titles",
        "button",
        "`whyWeAsk`",
        "the language the request itself is written in",
        "organization context",
        "Never mix languages",
    ):
        assert text in rule, text


def test_the_chat_guide_keeps_the_form_language():
    guide = " ".join(OPS_GUIDE.split())
    assert "written in the language the form is already written in" in guide
    assert "Only when the user asks for another language" in guide
    assert "organization context's form language" in guide
    assert "Never mix languages" in guide
    system = build_chat_system_prompt("{}", None)
    assert "the language the form is already written in" in " ".join(system.split())
