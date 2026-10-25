- A stack rolled back from 4.1 to 4.0.x now finishes what 4.1 left in the job queue instead
  of failing it as an unknown task. The two erasure jobs run for real: an account's stored
  provider credentials are deleted (`purge_provider_credentials`) and an old Google grant is
  revoked at Google (`revoke_google_grant`), both retried hourly for two days and logging ids
  and outcomes only. On 4.0 the purge deletes the stored credentials but does not revoke the
  grant at Google (4.1's Google service does); the provider service's request carries the
  account's email in its query string, as 4.0's account deletion does. 4.1's two periodic jobs (`sso_release_retry`,
  `recheck_verified_domains`) complete without doing anything and are not scheduled again.
- SSO connections that 4.1 marked `release_pending` (a deleted workspace's connection Polis had
  not released yet) can be read again after a rollback. They behave like disabled ones: they
  never sign anyone in, and no admin call acts on them.
