# Rotating the auth keys

Two secrets belong to the stack as a whole and sit in the settings store with the response
keyset (tier T4, section `auth_keys`):

| Setting | What it does |
|---|---|
| `AUTH_JWT_SECRET` | signs the session tokens (the cookies) and keys the HMACs of saved-draft links, list cursors, export download links and AI notices |
| `AUTH_AES_HEX_KEY` | a Fernet key (despite the name): seals the stored secrets of form actions, SCIM directories, registration services and webhooks, the OAuth and single sign-on state, and keys the sign-in code hash |

This runbook replaces either one **without losing data and, for the signing secret, without
signing everyone out**. The response keyset is another key with its own runbook:
[response-keyset-rotation.md](response-keyset-rotation.md).

## Why you may need to

Routine hygiene, a person with access to the settings leaving, or a suspected leak. Replacing a
key by hand (editing the store or the environment) would sign everyone out and make every stored
secret unreadable; these tasks avoid both.

## The idea: a key ring

Both settings hold a **ring** of one or two keys, current first: `<current>[,<previous>]`. The first
key signs and encrypts; every key in the ring verifies and decrypts. A stack that never rotates
has a ring of one, which is the plain key it always had. A rotation walks the ring:

| Ring | State |
|---|---|
| `[old]` | before |
| `[old, new]` | after **add_key**: the services read the new key, nothing uses it yet |
| `[new, old]` | after **promote**: new tokens and secrets use the new key, everything made before still reads |
| `[new]` | after **drop_old**: the old key is gone |

Each step is a task of the admin portal (Tasks), with a dry run first; the services restart
between steps so every one of them holds the ring (the tasks check this from the services'
heartbeats). Nothing prints a key: results, events, the audit trail and logs hold ids and counts.

## What each key covers

`AUTH_AES_HEX_KEY` seals these values at rest (all in the backend's database); `reencrypt` moves every
one of them to the new key:

| Table | Value |
|---|---|
| `forms`, `form_versions` | the secrets of a form's actions (Google Sheets credential, API tokens) |
| `actions`, `workspace_actions` | an action's own secrets and a workspace's copy of its credential |
| `scim_directories` | the secret SCIM webhooks are signed with |
| `registration_services` | the secret of a registration service |
| `form_webhooks` | a webhook's address and signing secret |

Short-lived values (OAuth and single sign-on state, sign-in codes, template preview tokens) need
no re-encryption: the ring reads them under either key for as long as both are in it.
Three kinds of **queued job** carry an argument sealed with the key (a credential purge, a Google
grant revocation, an account deletion); they are not rewritten: `drop_old` refuses while one is
queued or running. The response keyset, the Google OAuth credentials, drafts, feedback,
signature images and exports use the keyset, not this key.

`AUTH_JWT_SECRET` has nothing sealed to re-encrypt. Its effect on people:

* Access tokens (15 minutes) and the new refresh tokens move to the new key by themselves.
* A **refresh token** lives up to `REFRESH_TOKEN_EXPIRY_IN_DAYS` (30 by default) and is re-issued
  only when the browser refreshes explicitly, so a session that does not come back after the promote
  still holds a token signed with the old key. `drop_old` counts these sessions; dropping the key
  with some left signs those people out at their next visit. Waiting that many days after the
  promote makes the count zero without anyone noticing.
* **Saved-draft links and edit keys** made before the promote are hashes made with the old key.
  They cannot be re-derived, so they stop working when the old key is dropped. `drop_old` counts the
  unexpired drafts that hold one.

So: **adding and promoting a key signs nobody out.** Dropping the old signing secret does so only
for what the dry run counted, and only if you accept it.

## Before you start

1. **Every service runs a release with key-ring support** (4.3 or later): the backend, its jobs worker,
   the auth service and the Google Forms integration, and, if you run them, the Temporal worker and
   the actions executor. A service from before this release would read `<old>,<new>` as one key.
   The services report it in their heartbeat and `add_key` refuses while a running instance does not
   (`consumer_old_build`); the worker and the executor cannot report, so you confirm them
   (`ring_build_deployed`).
2. **Both keys are in the settings store** (they are, for a stack deployed with `deploy.sh`). A stack
   whose keys are only in environment files has to import them first (`settings-import`, see
   [admin-service.md](admin-service.md)); the tasks refuse `key_not_in_store`.
3. **The task runner can read them.** Rows written before this release do not list the runner among
   their readers; the tasks then refuse `key_not_readable_by_runner`. After every service runs the new
   release, once:

   ```bash
   docker compose -f docker-compose.deployment.yml run --rm --no-deps admin \
     /api/backend/.venv/bin/python -m backend.admin settings-grant-runner           # lists
   docker compose -f docker-compose.deployment.yml run --rm --no-deps admin \
     /api/backend/.venv/bin/python -m backend.admin settings-grant-runner --apply   # fixes
   ```

   It re-seals each key as its next version, unchanged, with the runner as a reader, and audits it.
   Run it **after** every service runs the new release: an older service refuses a row with a reader
   it does not know. It writes a new settings revision, so **restart every service afterwards**
   (backend, jobs worker, auth, Google Forms): the next task refuses `consumer_behind` or
   `consumer_restart_pending` until each one reports the new revision.
4. **No service takes the key from its own environment.** An `AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY` in
   a service's environment wins over the store, so the new key would never reach it (the tasks refuse
   `consumer_env_override`). Remove it from the stack file or `.env` (`settings-drift`, `settings-prune`).
5. **Back up the database** right before `reencrypt`, and keep the backup until the rotation is
   done:

   ```bash
   umask 077 && mkdir -p key-rotation
   docker compose -f docker-compose.deployment.yml exec -T app-postgres \
     pg_dump -U bettercollected -Fc bettercollected > key-rotation/postgres-before-rotation.dump
   ```

   (A dump holds values sealed with the old key until it is dropped. Store it like the live data.)
6. **Restarting.** After a task writes a key the services need a restart to read it. In the
   deployment stack:

   ```bash
   docker compose -f docker-compose.deployment.yml restart backend jobs-worker auth integrations-googleform
   ```

   (Swarm or another orchestrator: force-update each of those services.) Wait until the portal's
   Health page lists every instance as applied; a task refuses until it does
   (`consumer_restart_pending`, `consumer_behind`, `consumer_stale`, `consumer_not_reporting`).

## Rotating the encryption key (`which: aes`)

Open Tasks in the portal. Every mutating task needs a succeeded dry run with the same parameters.

| Step | Do | Parameters |
|---|---|---|
| 1 | `authkeys.add_key` | `which: aes`, tick `ring_build_deployed`. Note `added_key_id` in the result. |
| 2 | restart the services; give the workers and the executor the ring (below) | |
| 3 | `authkeys.promote` | `which: aes`, `new_primary_id` = `added_key_id`, tick `external_consumers_updated` (the workers and the executor hold the ring with the new key) |
| 4 | restart the services again; update the workers and the executor again | |
| 5 | back up; set the workers and the executor to `AES_HEX_KEY=<new>,<old>`; `authkeys.reencrypt` | `which: aes`, `primary_id` = `added_key_id`, tick `external_consumers_updated` (they hold the ring with the **new key first**) |
| 6 | `authkeys.verify` | `which: aes`: every value opens, counts per target, `jobs_pending` |
| 7 | `authkeys.drop_old` | `which: aes`, `keep_id` = `added_key_id`, tick `external_consumers_updated` and `jobs_on_postgres` |
| 8 | restart the services; set the workers and the executor to the single key | |

**The workers and the executor.** The Temporal worker and the actions executor each hold a copy of the
key as `AES_HEX_KEY` in their own environment; they cannot report to the store and are not restarted by
the steps above. The executor reads form-action secrets and writes a refreshed Google credential back,
so it must hold the ring from step 2 until step 8. What it writes back is sealed with its own key: the
backend opens it with its ring and seals it again with its current key (a value no key of the ring
opens is refused with a 422 and logged by ids), so an executor that still has the old key first does no
harm, but one that does not hold the new key cannot read what `reencrypt` moved. To read the ring from the store:

```bash
./deploy.sh settings-env-export --keys AUTH_AES_HEX_KEY --out key-rotation/ring.env
# the file holds AUTH_AES_HEX_KEY=<current>,<previous>: set the workers' AES_HEX_KEY to that value,
# restart them, then delete the file
```

**What `reencrypt` does.** It walks the seven tables in batches, decrypts each value that only the
previous key opens, encrypts it with the new key, checks that the result decrypts to the same text
with the new key alone, and writes it back only if the stored value has not changed since it was read
(a compare-and-swap under the row lock), then reads the row back before counting it. It is idempotent
and resumable: run it again after an interruption. Values it cannot open with either key are counted
(`values_unopenable`) and left; text that is not a token (an empty value) is left. `records_changed_concurrently`
means the application changed a value meanwhile: run again.

**What `drop_old` checks.** A full scan with the ring finds every value on the new key; none is unopenable;
the scan is not empty (an empty scan looks like a wrong database: `store_empty`, unless you tick
`allow_empty` for a stack that never stored such a value); no purge, revocation or deletion job is
queued or running in the Postgres queue (`jobs_pending`: wait a few minutes, or for the revocation's
two-day delay). The queue is the only place counted: a job routed to Temporal (`JOBS_BACKEND` or
`JOBS_BACKEND__<job>` set to `temporal`, off by default) is invisible to the task, so you confirm that none is
(`jobs_on_postgres`; `jobs_routing_unconfirmed` without it).

## Rotating the signing secret (`which: jwt`)

| Step | Do | Parameters |
|---|---|---|
| 1 | `authkeys.add_key` | `which: jwt`, tick `ring_build_deployed` |
| 2 | restart the services | |
| 3 | `authkeys.promote` | `which: jwt`, `new_primary_id` = `added_key_id` |
| 4 | restart the services again | |
| 5 | once every service has restarted: `authkeys.verify`, then wait and run it again to look | `which: jwt`: `sessions_on_previous`, `drafts_on_previous` |
| 6 | `authkeys.drop_old` | `which: jwt`, `keep_id` = `added_key_id`; `accept_sign_out` and `accept_draft_link_loss` when the counts above are not zero |
| 7 | restart the services | |

Step 5 is required: the counts start from the moment of the **first `verify` of the promoted ring** (the
verify records the database clock when its readiness check passes and the ring version it read, so a promote that
wrote the ring and then failed is the same promote). A `verify` refuses unless every instance has restarted onto
the settings revision of that version, so that run is the proof that no service signs with the old secret any
more. (Counting from the promote itself would miss a session refreshed after it by a service that had not
restarted yet: it still signs with the old key.)
Sessions refreshed between the promote and that verify are counted as old, so run it as soon as the restarts are
done; without one `drop_old` refuses (`promotion_not_verified`). Step 5 is also the choice. Waiting `REFRESH_TOKEN_EXPIRY_IN_DAYS` days after the promote leaves nobody on the old
key (every older refresh token has expired and unexpired drafts are bounded by their retention). Dropping
sooner signs out `sessions_on_previous` people and ends `drafts_on_previous` saved-draft links; the dry
run result says `ready: false` until you tick what you accept, and the real run refuses
(`sign_out_not_accepted`, `draft_links_not_accepted`) without it.

**An action-code compromise is not fixed by rotating the encryption key.** The actions executor runs creator
code and holds a copy of the key (`AES_HEX_KEY`); rotating `AUTH_AES_HEX_KEY` while the executor still
receives the new key gives whoever controls that code the new key too. Fix the executor first (isolate it, take
the key away from it, or redeploy it clean), then rotate.

**If a key leaked.** Do not wait: run steps 1 to 4, then `drop_old` with both statements. Everyone is
signed out at their next request and has to sign in again; the dry run shows how many. For the
encryption key, run all eight steps; until `drop_old` the old key is still in the ring.

## Refusals

| Code | Meaning | What to do |
|---|---|---|
| `key_not_in_store`, `key_not_readable_by_runner`, `keyset_unverified`, `ring_unreadable` | the key is not in the store, the runner may not read it, the row does not verify, or the value is not a ring of one or two keys | see "Before you start" 2 and 3 |
| `ring_build_unconfirmed`, `external_consumers_unconfirmed` | the statement was not ticked | tick it once it is true |
| `secret_has_separator` | the current signing secret contains a comma, which cannot be told from a ring | set a new comma-free secret by hand once (this signs everyone out), then use the tasks |
| `rotation_in_progress`, `no_rotation_in_progress` | `add_key` while a rotation is under way; any later step with no second key | continue or finish the rotation |
| `member_not_in_ring`, `primary_mismatch` | the id is not a key of the ring, or the kept key is not first (the promote has not happened) | use the id `add_key` reported; promote first |
| `consumer_not_reporting`, `consumer_stale`, `consumer_env_override`, `consumer_restart_pending`, `consumer_behind` | a service has not restarted onto the ring (or reports nothing, or takes the key from its environment) | restart; check the Health page |
| `store_not_configured`, `store_unreachable`, `store_empty` | the data store is not configured for the runner, does not answer, or holds no sealed value | see the runner's environment in [admin-service.md](admin-service.md) |
| `values_on_previous`, `values_not_readable` | values are still on the previous key, or no key opens them | run `reencrypt`; find the values (counts per table in the events) |
| `scan_incomplete`, `stale_version` | the scan was cancelled; the settings changed during the run | run again |
| `records_left_behind` (a failed `reencrypt`) | a record changed during the walk or did not read back as written, and still holds a value on the old key | start `reencrypt` again as a new run (a dry run first), not a resume of the failed one; the counts are in the run's events |
| `consumer_old_build` | a running instance reports a build without key-ring support | deploy the release to it |
| `promotion_not_verified` | no `verify` of this ring succeeded after the promote | restart the services, run `authkeys.verify` |
| `jobs_routing_unconfirmed` | the statement about Temporal-routed jobs was not ticked | tick it once it is true |
| `jobs_pending`, `counts_unavailable` | queued jobs hold a sealed argument; a count could not be read | wait; re-run the roles script (`postgres/ensure-admin-roles.sh`) if the count stays unavailable |
| `sign_out_not_accepted`, `draft_links_not_accepted` | the old signing secret still covers sessions or drafts | wait, or tick what you accept |

## Rollback

* The ring `[old, new]` or `[new, old]` reads everything made at any point of the rotation. If anything goes wrong, leave
  it as it is: nothing is lost.
* **Never go back to the old key alone after step 3** (the promote). Values and tokens made since are under the
  new key. Going back to the old key alone means restoring the pre-rotation backup, which loses everything
  written since.
* A failed restart of one service leaves it on the previous ring; the next step refuses until it is restarted.
* `drop_old` is the one step that cannot be undone from the portal. Every version of a key is kept sealed in
  `settings.history`, so a backup taken before the drop can still be read: unseal the older version with the
  settings master key (keep `SETTINGS_MASTER_KEY` as long as such a backup is kept).
* A stack that still holds a Mongo volume from the 4.0 import: values left in it are sealed with the old key.
  Keep the old key (stop before step 7) for as long as a rollback to 4.0 from that volume is possible.

## Upgrading to the release with key rings

The sign-in code hash and the PKCE verifiers of the Sheets and Google Forms OAuth flows are derived from the
encryption key as one parser now reads it: surrounding spaces and one pair of quotes removed. A key stored with
quotes or spaces therefore gives different codes and verifiers across the upgrade: a sign-in code or an OAuth
authorization started before it and finished after fails once and is started again. A key without them is
unchanged, and so is a single signing secret (it is used exactly as configured).

## Limits and notes

* In-flight sign-in codes (5 minutes) and OAuth authorizations (1 hour) started before a restart complete
  under either key.
* A failed (not retried) purge, revocation or deletion job that is re-queued by hand after `drop_old` carries an
  argument sealed with the dropped key and fails visibly; request the deletion again.
* The notices mail every admin (setting name, action, version, requester; never a key) for `add_key`,
  `promote` and `drop_old`.
* The tasks hold the locks `authkeys` and `keyset`: they never run beside a response keyset rotation.
