- Exporting a form's responses now runs on the server. Up to 5,000 matching responses download straight
  away; a larger export is prepared by a background job and fetched through a short-lived signed link
  (valid five minutes, for the person who asked, still needing `response.export`). The file is stored
  encrypted and can be downloaded again until 24 hours after it was built, when it is deleted (sooner
  with "Delete the file" on the page, or at once if responses of the form are deleted). Every export from the Export control, and every read of
  `GET .../forms/{form_id}/all-submissions`, leaves an audit entry (who, when, form, row count, columns,
  filters, whether it was a job; never an answer or the search text); API keys and MCP bulk reads are not
  audited yet. Exports are limited to 10 per user and form per hour, one live export per user and form,
  three jobs in flight per workspace, and 100,000 responses. The export takes the responses list's filters
  and a choice of columns (`POST .../forms/{form_id}/exports`); a form whose repeating groups export as
  tables comes as a ZIP of CSV files. Upgrade note: the jobs worker now also serves a new `exports` queue;
  if you set `JOBS_QUEUES`, include `exports`, or large exports stay queued.
