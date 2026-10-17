"""Rules AI form generation gets on top of its own schema (the outline
prompt, services/ai/outline_service.py)."""

# The language of a generated form. The yes/no answers are not text of the
# form: the respondent form shows them in the respondent's language.
LANGUAGE_RULES = """
## Language (always)
- Write the whole form in one language: the title, description, questions,
  descriptions, placeholders, choices, section titles, button and
  thank-you text and every `whyWeAsk`.
- That language is the one the request asks for. When it names none, use
  the language the organization context says its forms are written in, if
  it says so; otherwise the language the request itself is written in.
- Never mix languages, and never fall back to English for some of the text.
  Keep names, brands and terms the request quotes as they are.
- The answers of a `yes_no` question are fixed; do not give them choices.
"""
