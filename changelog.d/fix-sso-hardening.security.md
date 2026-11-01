- Single sign-on sessions now belong to the workspace and identity provider that
  signed them in: if a verified domain moves to another workspace that requires
  single sign-on, or the workspace replaces its identity provider, the old sessions
  no longer count and people sign in again. Sessions from before this change have
  no workspace recorded and sign in once more where single sign-on is required.
  Every request an owner makes through the email-code break-glass into a workspace
  that requires single sign-on is now recorded (session, user, method and route
  template, ids only, kept for a year) and shown, paged, on the single sign-on page;
  a failing audit write never blocks the owner.
