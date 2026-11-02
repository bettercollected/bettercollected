- A workspace can require an authenticator app for its members (owners only, behind `TOTP_ENABLED`,
  off by default). A member whose session has not presented a second factor gets "second factor
  required" on the workspace's pages and is sent to set one up or enter the code, in the same
  session: nobody is signed out. API keys and single sign-on sessions of the workspace are not
  asked. An owner sees how many members have set one up, and can remove a member's authenticator
  app (for people whose address is on one of the workspace's verified domains, or who belong to no
  other workspace); the platform administrator can remove anyone's. Both end that person's sessions
  and tell them by email, in English or Dutch. The email also tells an account when an app is
  added or turned off, when a recovery code is used and when the step is locked; each further lock
  before a correct code lasts longer (15 minutes, 1 hour, 6 hours, 24 hours).
