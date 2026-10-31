- Choice logic: single choice, multiple choice and dropdown questions can now
  show or hide individual options depending on earlier answers ("offer Wine
  only when the age is 18 or more"), and filter their options by an earlier
  choice question's answer ("only the cities of the chosen country"). The
  respondent page offers only the available options and clears a selection
  that stops being available, saying so politely; the server refuses an
  answer that selects an option that is not available, on submit and on the
  respondent's own edit. A question with nothing to choose is never required.
  Part of form spec v1 (`logic` on a choice, `optionFilter` on a question),
  the edit operations `set_option_logic` and `set_option_filter`, the public
  API, the MCP server and the SDKs.
