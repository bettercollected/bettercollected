- `GET /workspaces/{id}/forms/{form_id}/all-submissions` builds its answer in memory, so
  it now holds at most 5,000 responses. A form with more is refused with 413
  `too_many_rows`; use the export (up to 100,000 responses) for those. Smaller forms
  get the same answer as before.
