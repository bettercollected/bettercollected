# Rotating the response encryption keyset

`MASTER_ENCRYPTION_KEYSET` is the [Tink](https://developers.google.com/tink) AEAD keyset
(JSON, base64-encoded) that stored responses are encrypted with. This runbook replaces its key
without losing any data: add a new key as the primary, re-encrypt everything under it, then drop
the old key.

## Why you may need to

Earlier versions of this repository published a keyset: in `.env.deployment`, in
`webapp/README.md`, and as the CI test keyset (`.github/workflows/ci.yml`, which still uses it for
tests). A stack that copied it holds responses that anyone with a copy of the repository and of the
data (a database dump, a backup, a leaked volume) can decrypt.

Unlike `AUTH_JWT_SECRET` and `AUTH_AES_HEX_KEY`, the services do not refuse to start with it,
because a new keyset could not read the responses already stored. Instead every service that loads
the keyset logs a warning at startup. The warning names the variable and never its value:

```
MASTER_ENCRYPTION_KEYSET is a keyset that was published in the bettercollected repository, ...
```

Published keys are recognised by the SHA-256 of their key material
(`PUBLISHED_KEY_SHA256` in `common/common/services/keyset.py`), so re-encoding or reordering the
keyset does not hide one.

## What the keyset encrypts

| target (`--target`) | what | where |
|---|---|---|
| `responses` | `answers`, `hidden_fields`, `internal_answers` and each `respondent_feedback[].message` of every stored response | Postgres `app.form_responses` |
| `google-credentials` | the Google Forms integration's OAuth credentials | Postgres `google.oauth_credentials` |

The services that load the keyset: **backend**, **jobs-worker** and **integrations-googleform**.
Auth, the Temporal workers, the actions-executor and the webapp do not use it. (The Typeform
integration, a separate image that also loaded it, was removed in 4.1.)

## Before you start

- **Back up the database** right before you begin, and keep the backup until the rotation is
  finished and checked:

  ```bash
  umask 077 && mkdir -p keyset-rotation
  docker compose -f docker-compose.deployment.yml exec -T app-postgres \
    pg_dump -U bettercollected -Fc bettercollected > keyset-rotation/postgres-before-rotation.dump
  ```

  (`keyset-rotation/` is ignored by git. A Mongo backup or archive left from the 4.0 import is not
  covered by the rotation: see "Dropping a key once Mongo is retired".) The backup holds data encrypted with
  the published key: anyone with a copy and the repository can read it. Store it like the
  live data and delete it as soon as you no longer need it. Older backups have the same
  problem.
- **Keyset files are secrets.** The script writes them only to new files with mode 600 and never
  prints them. Don't paste them into tickets or chat, and keep them out of shell history.

Every command below runs from the checkout `deploy.sh` runs from (the directory holding the root
`.env`). `rotate` runs the script in a one-off backend container. That container has the backend's
environment (the current keyset, `DATABASE_URL`) and the stack's
network, with `keyset-rotation/` mounted for the keyset files:

```bash
umask 077
mkdir -p keyset-rotation
# The Google credentials live in the integration's own Postgres schema: let the script reach it
# as the integration's role.
export GOOGLE_DATABASE_URL="postgresql+asyncpg://bc_google:$(sed -n 's/^BC_GOOGLE_PASSWORD=//p' .env)@app-postgres:5432/bettercollected"
rotate() {
  docker compose -f docker-compose.deployment.yml run --rm --no-deps -T \
    --user "$(id -u):$(id -g)" -v "$PWD/keyset-rotation:/rotation" -e GOOGLE_DATABASE_URL \
    backend /api/backend/.venv/bin/python -m scripts.rotate_response_keyset "$@"
}
```

Each command prints a JSON report with key ids and counts only, and logs record ids and counts.
By default (`--store postgres`, which `auto` also means) it covers both targets in Postgres, the
only store since 4.1 (`DATABASE_URL`, or `GOOGLE_DATABASE_URL` for the Google credentials); no
write mode is read. `--store mongo` and `--store both` are refused (`store_retired`) before anything
connects, and values left in Mongo are not touched. For `reencrypt`, `--target` narrows the targets.
`drop-old` refuses both options and follows `keyset.drop_old`'s rule instead: it checks every target in
Postgres, configured, or refuses (`store_not_configured`), and refuses an empty store. It needs
`--mongo-retired`, which confirms that Mongo is retired and that values left in Mongo or its
backups become unreadable once the old key is dropped; without it the command refuses
(`store_retired`), since Mongo is not scanned. Unlike the task, the script cannot check the services'
heartbeats (`write_stores` in `settings.service_state`) itself: before passing `--mongo-retired`,
check there that no live backend or Google integration instance still writes Mongo (or reports
nothing), for example with a dry run of `keyset.drop_old` with `mongo_retired`, which checks it.

**The script only writes with the deployed keyset.** `reencrypt` (other than `--dry-run`) and
`drop-old` check that the primary key of `--keyset-file` is the primary of the
`MASTER_ENCRYPTION_KEYSET` in the container's environment. If it isn't, they stop with an error and
change nothing. `rotate` starts a new container each time, so after step 3 it already has the new
keyset from the root `.env`.

## The rotation

### 1. Count

```bash
rotate reencrypt --dry-run
```

Shows, per target and store, how many records and encrypted values there are and which key ids
they use (`values_key_<id>`).

### 2. Add a key

```bash
rotate add-key --out /rotation/rotated.keyset
```

This reads the current keyset from the backend's environment. It writes a new keyset to
`keyset-rotation/rotated.keyset`: the current keys, plus a new AES-256-GCM key as the primary. The
old keys stay so everything stored keeps decrypting. Note the printed `primary_key_id`: that is the
new key.

### 3. Give every service the new keyset

This comes **before any re-encryption**. A service still on the old keyset cannot read a value
re-encrypted under the new key: answers would fail to load and Google imports would fail.

```bash
cp .env keyset-rotation/env.before-rotation
new=$(cat keyset-rotation/rotated.keyset)
awk -v value="$new" '/^MASTER_ENCRYPTION_KEYSET=/ { print "MASTER_ENCRYPTION_KEYSET=" value; next } { print }' \
  .env > .env.rotating && mv .env.rotating .env && chmod 600 .env
unset new
./deploy.sh          # or: docker compose -f docker-compose.deployment.yml up -d backend jobs-worker integrations-googleform
```

If your stack is deployed another way (Docker Swarm, Kubernetes), set the new value wherever those
services get `MASTER_ENCRYPTION_KEYSET`, and roll them all.

Check that each one restarted with it. The startup warning changes from "is a keyset that was
published" to "still holds a key that was published ... (no longer the primary)":

```bash
docker compose -f docker-compose.deployment.yml logs --since 15m \
  backend jobs-worker integrations-googleform | grep MASTER_ENCRYPTION_KEYSET
```

From now on, new responses are encrypted with the new key.

### 4. Re-encrypt

```bash
rotate reencrypt --keyset-file /rotation/rotated.keyset --dry-run
rotate reencrypt --keyset-file /rotation/rotated.keyset
```

This walks every record in batches by id (`--batch-size`, default 200). It decrypts each value not
yet under the primary key, encrypts it with the primary key, checks that the result decrypts to the
same bytes, and writes it back only if the stored value has not changed since it was read.

- **Idempotent and resumable.** Values already under the primary key are skipped without being
  decrypted, because a Tink ciphertext starts with its key id. After an interruption, run the same
  command again. `--start-after <id>` skips the ids an earlier run logged as done, and `--limit N`
  re-encrypts at most N records, for a first careful run.
- `records_changed_concurrently`: the application changed a value meanwhile. Run again.
- Each value finds its own context. A response stored before responses carried their workspace is
  tried against each workspace its form is linked to, value by value, so a record whose values
  were encrypted for different workspaces is still re-encrypted whole.
- `records_unopenable` / `values_unopenable`: no candidate context decrypts a value. Its
  workspace is unknown and none of its form's workspaces opens it, for example a response whose
  form was removed from every workspace. The record ids are in the log. Such values stay under the
  old key, and step 5 refuses while they do. Either keep the old key (stop before step 5) or delete
  those records. The other values of the same record are still re-encrypted. Another cause: a
  feedback message stored as plaintext because it started with `v1:` (before `encrypt` stopped
  passing such values through). It only looks like ciphertext.
  `python -m scripts.check_undecryptable_values` counts these (read-only).

Repeat the dry run until it reports `values_stale` as 0 (or absent) for every target and store.

### 5. Drop the old key

```bash
rotate drop-old --keyset-file /rotation/rotated.keyset --out /rotation/final.keyset --mongo-retired
```

This scans every target in Postgres. It **refuses**, writing nothing, when:

- any value still uses a key other than the primary (the report shows the counts per key id);
- any target holds **no records at all**. An empty store may mean the script is
  reading the wrong database, for example a `DATABASE_URL` or
  `GOOGLE_DATABASE_URL` that didn't reach the container. Dropping the old key then would make the
  real data unreadable. The report's `records` lists each target's count per store. If a store
  really is empty (for example, the stack never used the Google Forms integration), check that
  count, then run again with `--allow-empty`;
- the keyset file is not the deployed one (see above).

Otherwise it writes `keyset-rotation/final.keyset`, which holds the primary key only.

### 6. Give every service the final keyset

As in step 3, with `keyset-rotation/final.keyset`. Then check that no service logs the
`MASTER_ENCRYPTION_KEYSET` warning.

### 7. Clean up

- Take a fresh backup. Delete the pre-rotation backups and any older ones as soon as your
  retention allows: they are readable with the published key.
- Keep `rotated.keyset` somewhere safe until you are sure nothing needs the old key (see
  Rollback), then delete it, `env.before-rotation` and the rest of `keyset-rotation/`.
  `final.keyset` is now in the root `.env` and needs no separate copy there.

## Rollback

- **The combined keyset (`rotated.keyset`) reads everything** at every point of the rotation: old
  values and new ones. If anything goes wrong, give every service the combined keyset (step 3).
  That is always safe.
- **Never go back to the old keyset alone after step 3.** Responses submitted since then, and
  everything re-encrypted, are under the new key, and the old keyset cannot read them. Going back to
  old-key-only means restoring the pre-rotation backup, which loses everything written since.
- **After step 6**, a value under the old key can turn up again, for example from a restored
  backup. Give the services `rotated.keyset` again, run `reencrypt`, then
  `drop-old`.
- `drop-old` and the final keyset never touch stored data. Only `reencrypt` writes, and it writes
  only values that decrypt back correctly.

## Rotating with the admin tasks

When the keyset lives in the settings store (tier T4, changed by tasks only) the rotation is five
tasks of the admin task runner instead of the script. Each is a task with typed parameters; a
mutating one needs a succeeded dry run of the same parameters first. The keyset never appears in a
parameter, result, event, audit row or log: only key ids and counts.

| Step | Task | What it does |
|---|---|---|
| 1 | `keyset.add_key` | adds a new AES-256-GCM key as a SECONDARY (the primary does not move); refuses while a rotation is under way (more than one key) |
| 2 | (restart the services) | they pick up the new keyset and report its key ids in their heartbeat |
| 3 | `keyset.promote` (`new_primary_id`) | makes that key the primary; refuses a key that was published |
| 4 | (restart the services) | |
| 5 | `keyset.reencrypt` (`primary_id`) | moves every value to the primary: resumable, idempotent, compare-and-swap writes, each record read back before it is counted; `stores: postgres` (the default; `auto` means the same) follows the store rule below; refuses a published primary. Starting an apply run mails all admins (`settings.keyset_reencrypt` in the admin outbox: run id and primary key id); a dry run mails no one |
| 6 | `keyset.verify` | read-only full scan: every value opens; counts per key id (events `kid_<id>`) |
| 7 | `keyset.drop_old` (`mongo_retired`) | removes the other keys only when a full scan of EVERY target in Postgres (configured, else `store_not_configured`) finds no value on them, and only with `mongo_retired` (see "Dropping a key once Mongo is retired" below; `store_retired` without it). The scan decrypts with the primary key ALONE, so a value the final keyset could not open also stops it (`values_not_readable`). The responses must be there (an empty Google credentials store needs `allow_empty_google`) |

**The store rule.** Postgres is the only store the tasks read or write (since 4.1): `DATABASE_URL`
for the responses and `GOOGLE_DATABASE_URL` for the Google credentials, which must be configured
(else `store_not_configured`). `stores: postgres` (the default) and `stores: auto` (kept so that
parameters saved before 4.1 still validate) cover it. `stores: mongo` and `stores: both` are refused with
`store_retired` before anything connects, even when the runner still has a `MONGO_URI` (which it
never uses). No write mode is read: the runner's `DB_WRITE_MODE*` are ignored. The same rule applies
to `reencrypt`, `verify` and the `responses.*` and `google.*` tasks and to the break-glass scripts.

**Dropping a key once Mongo is retired.** `drop_old` scans Postgres alone, so it needs `mongo_retired`:
a signed, audited statement (it is part of the signed run request and of the
request's audit row, and needs its own dry run) that Mongo is retired. Without it the task refuses
with `store_retired`. It also needs every live backend and Google integration instance to report, in
its settings heartbeat, that it writes Postgres alone (`write_stores`, from the service's own
`DB_WRITE_MODE*`; admin revision 0018).
An instance that still writes Mongo refuses with `consumer_writes_mongo`, one that does not report
it (a build from before) with `consumer_write_stores_unknown`; the check runs again right before
the key is written. It also refuses (`import_incomplete`) until the import from 4.0 is over: while the runner has a
`MONGO_URI`, or while `migration_progress` records an unfinished backfill of the responses (or of
the forms' links), since a later backfill could bring in a value on the dropped key. Values left in Mongo, or in a Mongo backup or archive,
are unreadable once the old key is dropped: keep the old keyset for as long as such an archive is
kept.

`drop_old` has no target or store parameters on purpose, and a scan that did not finish (cancelled)
refuses. A Google credentials store that is empty because the integration was never used needs
`allow_empty_google` together with `google_in_use: false` (the combination `allow_empty_google` with
`google_in_use: true` is refused); the responses store is never accepted empty. Values no candidate workspace
opens stay where they are and are counted (`values_unopenable`); `drop_old` then refuses.

**Readiness.** `promote`, `reencrypt` and `drop_old` first check the settings store's service
heartbeats (`settings.service_state`) for the services that read the keyset (the backend, and the
Google integration unless `google_in_use` is false; a Google instance that does report is always
checked): every instance reported in the last 2 minutes
(an instance seen within the last 15 minutes that has stopped reporting is treated as possibly
still running and refuses; older ones are taken as gone), holds a keyset with exactly the stored
key ids (the heartbeat's `keyset_fp`, a hash of the key ids), has restarted onto the current
settings revision (`restart_pending` false, `revision_applied` at least the store's revision) and
does not override the keyset from its environment. The fingerprint does not say which key is
primary, so after a promote the revision and restart flag are what show a service runs it. The
refusals are `consumer_not_reporting`, `consumer_stale`, `consumer_missing_key`,
`consumer_restart_pending`, `consumer_behind` and `consumer_env_override`.

**Typeform.** The Typeform integration was removed in 4.1. `promote`, `reencrypt` and
`drop_old` accept and ignore `typeform_acknowledged`, and `drop_old` no longer waits for a
Typeform heartbeat.

**Where the new keyset is written.** The runner has no write privilege on the settings tables and
no access to the audit log. It seals and signs the new row itself (for the keyset's section only),
builds and hashes the audit row (it holds the audit key, the database never does) and calls
`settings.task_write_keyset` (migrations 0009 and 0015), which accepts only this key, one version up,
under the writer lock, with a matching signed manifest, **for a `running` apply run of the matching
`keyset.*` task whose start (`task.run.started`) the runner's audit function recorded, once per
run**, and writes the audit row (`settings.task_set`, actor kind `system`, the requesting admin in
the detail) itself from parameters it validates. The same transaction enqueues a
`settings.keyset_changed` notification for all admins (setting name, action, version and requester;
never a value) in the admin outbox. The database cannot verify an HMAC, so a row signed wrongly is
written but refused by every reader and reported by `settings-verify` and the integrity loop; what
the checks above prevent is a database credential alone (the runner's, without a run) producing a
write at all.

**Requirements and limits.** The keyset must be in the settings store (imported with the admin
import command) and the runner must be a reader of it. A keyset row imported before the runner
became a reader is hidden from the runner: the tasks refuse with `keyset_not_readable_by_runner`.
Its readers are part of the signed row, so only the admin service can fix it by re-writing the
row with the runner among its readers; do not edit the table. Stacks whose services still take the
keyset from the environment keep using the script above.

**Old keys are kept for backups.** `settings.history` keeps every version of the keyset, never pruned
and never changed (the history guard refuses deleting or updating any row of a task-managed key, for
the migration role and the portal's writer alike; a master-key rotation appends a re-wrapped copy to
`settings.history_wraps` and leaves the original), and `settings-verify` reports a version that no
stored copy opens (`history_unreadable`). After `drop_old` the dropped key therefore stays recoverable from the
sealed history, so a database backup taken before the re-encryption can still be read: unseal the
older version with the settings master key. Purging old keys is a deliberate database operation by
the owner role (`ALTER TABLE settings.history DISABLE TRIGGER history_guard`, delete the versions,
re-enable it), best done only after the last backup that needs them has expired. `SETTINGS_MASTER_KEY`
must be kept as long as those backups are.

**Notices.** Every keyset write (`add_key`, `promote`, `drop_old`) and the start of a `reencrypt`
apply run enqueue one outbox row for all admins: setting name, tier, action, version, requester,
run id and the key ids or counts involved (never a key).
