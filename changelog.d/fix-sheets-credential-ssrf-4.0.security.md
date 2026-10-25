- Google Sheets action: adding the action with caller-supplied secrets is refused (422
  `action_secrets_not_allowed`, nothing is written); only the Google Sheets connection flow
  stores its credential. Other actions still take secrets.
- Google Forms service and actions executor: Google access tokens are refreshed only at Google's
  token endpoint (the configured `GOOGLE_TOKEN_URI` in the Google Forms service, including
  google-auth's own refresh; in the actions executor, Google's documented endpoints). The token
  address stored inside a credential is no longer trusted, so a forged credential cannot make
  either service send a client secret and refresh token to another host.
- The Google Sheets credential now travels from the backend to the Google Forms service in the
  request body instead of the query string, so it no longer reaches access logs. Backend and
  Google Forms service must run the same release.
