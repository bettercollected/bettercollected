- Single sign-on sessions now belong to the workspace whose identity provider signed
  them in: if a verified domain moves to another workspace that requires single
  sign-on, the old sessions no longer count there and people sign in again. Sessions
  from before this change have no workspace recorded and sign in once more where
  single sign-on is required. Owner break-glass sign-ins to a workspace that
  requires single sign-on are now written to the audit log (once per session and
  hour).
