- Google Sheets action: the backend can run the action's Google authorization and create the
  spreadsheet itself, with the Google sign-in client and only the `drive.file` scope (access to the
  files the app creates), without the Google Forms service. Off by default: set
  `GOOGLE_SHEETS_OAUTH=backend` after registering the redirect address and the scope on the sign-in
  client (docs/RUNNING_INTEGRATIONS.md). Stored credentials keep their format.
