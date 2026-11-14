- Saved views of a form's report (behind `REPORTING_ENABLED`). The Report page has a views bar:
  open a saved view, save the report on screen as one, update it, rename it, share it and
  delete it. A view is private to its maker by default; someone who may edit the form can
  save a view for everyone who can open the report. A view stores only a name and a validated
  definition (question ids, dates, enums: never an answer or a respondent). New routes
  `GET` and `POST /workspaces/{id}/forms/{form_id}/report/views` and `GET`, `PATCH` and `DELETE
  .../report/views/{view_id}`, a new table (revision 0040), and audit entries for what the
  whole form shares (`report_view_created`, `_updated`, `_deleted`, `_shared`, `_unshared`),
  in English and Dutch.
