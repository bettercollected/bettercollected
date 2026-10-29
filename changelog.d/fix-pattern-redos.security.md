- Answer patterns are no longer evaluated by the respondent's browser. The server
  matches them with RE2 in linear time, but the form also tested them in the browser
  with a backtracking engine, where a pattern such as `^(a+)+$` could freeze a tab on
  one unlucky answer. The browser now checks only the built-in formats and "whole
  numbers only"; a custom pattern is checked when the answer is submitted, and the
  respondent is taken back to the question with the message. A pattern RE2 cannot
  use (a lookaround, a backreference, a mistake) is now refused when a form is saved,
  through the builder, the API, the AI assistant and the Open Formulieren import
  (the import lists it as not carried); patterns already stored are kept.
