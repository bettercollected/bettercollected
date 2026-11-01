- A workspace that requires single sign-on now refuses a session that did not sign in
  with SSO on every request (403 `sso_required`), not only when the session next
  refreshes, so turning the requirement on takes effect at once instead of up to
  15 minutes later. Owners keep email-code sign-in as break-glass, guests on other
  domains and API keys are unaffected, and nothing changes while single sign-on is
  off. The dashboard sends the user to the workspace selection to sign in with SSO.
