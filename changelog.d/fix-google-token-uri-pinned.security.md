- Actions and Google Forms: Google access tokens are refreshed only at Google's token endpoint
  (the configured `GOOGLE_TOKEN_URI` in the Google Forms service; in the actions executor,
  Google's documented endpoints). The token address stored inside a credential is no longer
  trusted, so a forged credential cannot make either service send its client secret and refresh
  token to another host. Stored credentials are unchanged.
