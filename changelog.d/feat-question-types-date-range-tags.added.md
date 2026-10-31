- Two more question types: a date range (a first and a last day, the last not before the
  first, with the same date rules as a date question for both ends) and tags (short
  free-entry labels, with a lowest and a highest number of tags and a longest tag). They work
  in the builder (in English and Dutch), the form respondents fill in, the response views, the
  CSV export (a range as `start/end`, tags in one cell), logic conditions, field rules and
  calculations (a range reads as its start and its end), the public API, the MCP server and
  both SDKs. The server checks every answer. Like the other new question types, they are
  behind `NEW_QUESTION_TYPES_ENABLED`, which is off by default.
