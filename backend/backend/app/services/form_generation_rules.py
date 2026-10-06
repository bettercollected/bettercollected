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
