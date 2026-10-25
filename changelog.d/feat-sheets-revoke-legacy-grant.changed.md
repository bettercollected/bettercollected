- Google Sheets action: with `GOOGLE_SHEETS_OAUTH=backend`, reconnecting an action that held a
  grant from before `drive.file` stores the new credential and clears its reconnect marks in one
  write, removes every stored copy of the old credential, and revokes the old grant at Google. A
  failed revocation never blocks the new grant; a `revoke_google_grant` job retries it hourly for
  two days (`JOBS_BACKEND__revoke_google_grant=postgres`) and shows in the integrity monitor when
  still pending after a day. An old grant issued to the sign-in client itself is deleted but not
  revoked, since revoking it would end the new grant too.
