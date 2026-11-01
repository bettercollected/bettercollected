- Single sign-on sessions now belong to the workspace and identity provider that
  signed them in: if a verified domain moves to another workspace that requires
  single sign-on, or the workspace replaces its identity provider, the old sessions
  no longer count and people sign in again. Sessions from before this change have
  no workspace recorded and sign in once more where single sign-on is required.
  Owner break-glass sign-ins to a workspace that requires single sign-on are now
  recorded in an audit table (ids only, kept for a year), shown on the single
  sign-on page, and written to the log.
