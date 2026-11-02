- Responses can be imported from a CSV file (`CSV_IMPORT_ENABLED`, off by default; Owner and Admin, new permission
  `response.import`). A file exported from the same form imports as it is. The columns are matched to the questions, a
  dry run checks every row with the respondent rules and stores nothing, and the import is all or nothing. Imported
  responses are anonymous, are marked as imported, trigger no mails, webhooks or other actions, and the whole import
  can be undone for 14 days. The uploaded file is kept encrypted only until the import has run (an hour at most) and
  the audit entry never holds a value. See `docs/response-import.md`.
