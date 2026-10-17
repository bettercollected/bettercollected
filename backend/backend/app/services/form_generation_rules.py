"""Rules every AI form generator gets on top of its own schema.

Shared by the OpenAI, Gemini and OpenAI-compatible generators so a generated
form starts out honest (services/publish_checks.py holds the publish rules)."""

HONEST_FORM_RULES = """
## Honest defaults (always)
- Consent and opt-in questions are explicit choices the respondent makes:
  never pre-selected, never bundled with other agreements, and declining is
  as easy as agreeing.
- Every question asking for an email address, a phone number or an ID number
  sets `properties.whyWeAsk`: one short, plain sentence telling the
  respondent why it is needed.
- No urgency, pressure or guilt in any text (titles, buttons, thank-you).
"""

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

# Section titles of generated pages (properties.sectionTitle): optional, so a
# form without them still reads well (the page's heading or first question
# stands in).
SECTION_TITLE_RULES = """
## Section titles (optional)
- A top-level field may set `sectionTitle`: a short, plain name for that
  page's section, e.g. "About your visit" or "Your contact details". The
  Leaflet style shows every page as a numbered section with this name in its
  section bar and in the contents list on the welcome page; without one it
  shows the page's heading or first question.
- Set it on multi-page forms when it helps respondents see where they are;
  leave it out when the page's title already says it, and on single-page
  forms.
- A few everyday words (B1 level), at most 120 characters (ideally under
  40), no numbering (the section number is added), no jargon.
"""
