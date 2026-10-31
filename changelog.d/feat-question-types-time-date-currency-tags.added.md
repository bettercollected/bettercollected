- Three new question types: a time (HH:MM, with an earliest and a latest time), a day
  typed as day, month and year (with the same date rules as a date question) and an amount
  of money with its currency (one or more currencies, a lowest and a highest amount). They
  work in the builder (in English and Dutch), the form respondents fill in, the response
  views, the CSV export, the public API, the MCP server and both SDKs, and as sources in
  logic, field rules and calculations. The server checks every answer.
- `NEW_QUESTION_TYPES_ENABLED` (off by default) switches the new question types on for
  creators: while it is off, the Insert menu leaves them out, and saving a new one, or
  changing the settings of one a form already has, is refused (422 `question_type_disabled`;
  the same for the API, MCP, the AI assistant, templates and imports). Questions a form
  already has keep working: they are shown, answered and exported.
