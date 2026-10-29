- The respondent form no longer tests answer patterns written by a form's creator in the
  browser. The server matches them with RE2 in linear time, but the browser used a
  backtracking engine, where a pattern such as `^(a+)+$` could freeze a tab on one
  unlucky answer. The browser now checks only the built-in formats and "whole numbers
  only"; a custom pattern is checked when the answer is submitted, and the respondent is
  taken back to the question with the message next to it.
