- A dropdown or multiple choice question can take its options from a workspace list (reference data
  with an optional group per item, CSV import and export, managed by whoever can edit forms) or from the
  answers given to a question of another form of the same workspace. Everything is read on the server;
  a respondent receives only the labels, searchable and paged. A dependent list follows an earlier
  question's answer through the items' groups. Another form's answers are used only from a question whose
  creator turned on "answers may be shown as choices in other forms" (off by default; respondents
  are told next to the question), and only answers given while that was on; the saver also needs
  permission to read that form's responses. Answers from respondents with a deletion request,
  anonymous submissions and expired responses are never offered. The server checks every chosen option when a
  response is submitted or a choice is changed, stores a label snapshot beside it that exports,
  webhooks, email actions and the Google Sheets action show, and refuses an option that is no longer
  offered. It is behind `OPTION_SOURCES_ENABLED`, which is off by default. See
  `docs/option-sources.md`.
