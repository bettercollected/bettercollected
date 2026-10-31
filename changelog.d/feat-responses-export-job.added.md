- Exporting a form's responses now runs on the server. Up to 5,000 matching responses download straight
  away; a larger export is prepared by a background job and fetched through a short-lived signed link
  (valid five minutes, for the person who asked, still needing `response.export`). The file is stored
  encrypted, deleted at its first complete download or after 24 hours, and at once if responses of the
  form are deleted. Every export leaves an audit entry (who, when, form, row count, columns, filters,
  whether it was a job; never an answer or the search text). Exports are limited to 10 per user and
  form per hour, and to 100,000 responses. The export takes the responses list's filters and a choice
  of columns (`POST .../forms/{form_id}/exports`); a form whose repeating groups export as tables
  comes as a ZIP of CSV files. Upgrade note: the jobs worker runs the new `build_response_export`
  job on the `default` queue.
