- **Answer pipes in the form builder and on respondent pages are read in linear time.** A question title,
  description or ending holding `{{field:` followed by a very long run of spaces made the pattern that finds pipe
  tokens backtrack until the browser tab froze, for the creator in the builder and for a respondent opening the
  form. The patterns now cut the key at `|` or a brace and trim it in code, as the server does.
