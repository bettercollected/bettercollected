- Google Sheets action: with `GOOGLE_SHEETS_OAUTH=backend`, a stored credential granted before
  `drive.file` (full Drive access) is no longer used. On its next use the action's run is skipped
  and counted, the action is marked `needs_reconsent`, and the workspace's billing owner gets one
  mail (English or Dutch) asking to reconnect Google Sheets. `python -m backend.sheets_legacy`
  counts the actions concerned (read-only).
