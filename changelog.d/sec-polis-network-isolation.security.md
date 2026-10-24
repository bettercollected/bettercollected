- Single sign-on: Polis no longer shares one network with all its callers. The SSO overlay gives
  the backend, the jobs worker and auth each an internal network of their own with Polis, and
  Polis's internet egress goes over a network of its own with a pinned subnet
  (`POLIS_EGRESS_SUBNET`, default `172.30.78.0/29`). Local development runs Polis with its own
  Postgres instead of joining the local stack's network (the old `polis` database in
  `app-postgres` is no longer used). Before enabling SSO on a hosted stack, filtering Polis's
  egress to private, link-local and loopback addresses is now a required step: see "Polis egress"
  in `docs/sso.md`; `deploy.sh` reminds you when SSO is on.
