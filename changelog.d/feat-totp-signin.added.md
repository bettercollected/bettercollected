- Signing in with an authenticator app: an account that has set one up (behind `TOTP_ENABLED`, off by
  default) is asked for a code, or a recovery code, after its email code or Google sign-in, before a
  session is created. The session records it and its tokens carry it. Single sign-on sessions and
  respondent sessions are not asked. While the setting is off, sign-in is exactly as before.
