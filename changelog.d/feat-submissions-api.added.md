- Submit responses through the public API (`POST /forms/{formId}/submissions`, and `PATCH` to change
  one a key made itself), with a new API key scope `submissions:write` that no other scope implies.
  A submission goes through the same checks, storage and follow-up as a respondent's (published
  version only, open and close dates, response limit, validation, retention, encryption, actions,
  webhooks and email actions). A key is not a respondent: no identity or receipt is stored, forms that
  ask for a verified respondent refuse it, the caller asserts the respondent's consent, and the
  response records that the key made it (staff see it, respondents never do). Files and signatures
  are not accepted yet. The Python and TypeScript SDKs and the command line have `submit` and
  `update-submission`. A webhook body has a new `source` member (`"api"`) for such a response. A key's
  update is refused once the form is closed, not open yet, needs a verified respondent or is private.
  It is behind `SUBMISSIONS_API_ENABLED`, which is off by default (the endpoints answer 404 and the
  scope can't be granted).
