- Google Forms: a stored Google credential is never written unencrypted. Legacy rows
  connected by older versions have no user id to derive the encryption key from, and every
  token refresh stored their access and refresh tokens in plain text; such an update now
  writes nothing, and reconnecting gives the row the signed-in user's id. An update without
  a stored credential no longer fails. Operators: delete the remaining legacy rows once, as
  described in `docs/postgres-cutover-runbook.md` ("Google credentials without a user id").
