- Exports in more formats: `POST .../exports` takes a `format`, `csv` (as before), `xlsx` or `json`. The
  other formats take the same columns, filters, limits, permission and audit as a CSV export, large
  exports are still prepared in the background, and nothing is held in memory or written to disk while
  the file is made. In the Excel file, text is never a formula (a cell that starts with `=`, `+`, `-` or
  `@` stays as written and is flagged as text), the submission time and date answers are real dates,
  and a repeating group exported as a table is a sheet of its own. The JSON follows the REST API's
  response shape and says what each question is.
- The PDF of one response: `GET /workspaces/{id}/submissions/{response_id}/pdf` draws the form's title,
  when it was submitted (in the viewer's time zone), and every question with its answer, in English or
  Dutch, with page numbers and a tagged structure, for people who may read the response. It is made
  when asked and never stored, rate limited and recorded in the export audit (who and which response,
  never its content). Internal fields are not printed, files are listed by name, and a drawn signature
  is listed rather than drawn.
