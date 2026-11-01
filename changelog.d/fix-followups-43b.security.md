- The actions executor's database role is kept from creating temporary tables by
  `postgres/ensure-jobs-exec-role.sh` itself (it revokes TEMPORARY from PUBLIC and gives
  it back by name to the service roles), not only by `ensure-admin-roles.sh`. The
  trigger-function owner `bc_jobs_def` is reset to the grants the queue's triggers need.
  The executor refuses to start when its role can create temporary tables or is a member
  of any role (it could switch to `bc_jobs_def`), or when `bc_jobs_def` holds a privilege
  in another service's schema; the script repairs all of these and exits non-zero if a revoke did not take. A stack that has not
  yet run `postgres/ensure-admin-roles.sh` or this script since 4.1 re-runs the script
  before updating the executor image (`deploy.sh` does it on every deploy).
