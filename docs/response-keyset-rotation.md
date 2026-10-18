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
| `responses` | `answers`, `hidden_fields`, `internal_answers` and each `respondent_feedback[].message` of every stored response | Mongo `form_responses` (`MONGO_DB`), Postgres `app.form_responses` |
| `google-credentials` | the Google Forms integration's OAuth credentials | Mongo `Oauth2CredentialDocument` (`GOOGLE_MONGO_DB`, default `bettercollected_googleform`), Postgres `google.oauth_credentials` |

The services that load the keyset: **backend**, **jobs-worker**, **integrations-googleform**,
and **integrations-typeform** (a separate image). Auth, the Temporal workers, the
actions-executor and the webapp do not use it.

The Typeform integration is not part of this repository, so the script does not re-encrypt data
it stores. If you run it and it stores data with the keyset, keep the old key (skip "Drop the old
key") or reconnect the Typeform accounts after dropping it.

## Before you start

- **Back up both databases** right before you begin, and keep the backups until the rotation is
  finished and checked:

  ```bash
  umask 077 && mkdir -p keyset-rotation
  docker compose -f docker-compose.deployment.yml exec -T mongodb \
    mongodump --username root --password root --authenticationDatabase admin --archive --gzip \
    > keyset-rotation/mongo-before-rotation.archive.gz
  docker compose -f docker-compose.deployment.yml exec -T app-postgres \
    pg_dump -U bettercollected -Fc bettercollected > keyset-rotation/postgres-before-rotation.dump
  ```

  (Use your own Mongo credentials if you changed them. `keyset-rotation/` is ignored by git.) These backups hold data encrypted with
  the published key: anyone with a copy and the repository can read them. Store them like the
  live data and delete them as soon as you no longer need them. Older backups have the same
  problem.
- **Drain the Postgres mirror outbox** if you run in a dual write mode
  (`python -m backend.migrate reconcile`, see `docs/postgres-cutover-runbook.md`), and do not
  change `DB_WRITE_MODE` during the rotation.
- **Keyset files are secrets.** The script writes them only to new files with mode 600 and never
  prints them. Don't paste them into tickets or chat, and keep them out of shell history.

Every command below runs from the checkout `deploy.sh` runs from (the directory holding the root
`.env`). `rotate` runs the script in a one-off backend container. That container has the backend's
environment (the current keyset, `MONGO_URI`, `DATABASE_URL`, `DB_WRITE_MODE`) and the stack's
network, with `keyset-rotation/` mounted for the keyset files:

```bash
umask 077
mkdir -p keyset-rotation
# The Google credentials live in the integration's own Postgres schema: let the script reach it
# as the integration's role. Skip this if the stack does not use Postgres yet.
export GOOGLE_DATABASE_URL="postgresql+asyncpg://bc_google:$(sed -n 's/^BC_GOOGLE_PASSWORD=//p' .env)@app-postgres:5432/bettercollected"
rotate() {
  docker compose -f docker-compose.deployment.yml run --rm --no-deps -T \
    --user "$(id -u):$(id -g)" -v "$PWD/keyset-rotation:/rotation" -e GOOGLE_DATABASE_URL \
    backend /api/backend/.venv/bin/python -m scripts.rotate_response_keyset "$@"
}
```

Each command prints a JSON report with key ids and counts only, and logs record ids and counts.
By default it covers both targets and the stores the services write, following `DB_WRITE_MODE`
and its `__responses` / `__google` overrides. For `reencrypt`, `--target` and
`--store mongo|postgres|both` narrow or override that. `drop-old` refuses both options: it always
checks every target in every store the services write.

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
./deploy.sh          # or: docker compose -f docker-compose.deployment.yml up -d backend jobs-worker integrations-googleform integrations-typeform
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
- **Dual write modes.** The primary store's new ciphertext is copied byte for byte to the mirror,
  so the two stores stay identical (`backend.migrate verify` stays clean). The mirror is then swept
  for rows that differed or exist only there.
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
rotate drop-old --keyset-file /rotation/rotated.keyset --out /rotation/final.keyset
```

This scans every target in every store the services write. It **refuses**, writing nothing, when:

- any value still uses a key other than the primary (the report shows the counts per key id);
- any target in any store holds **no records at all**. An empty store may mean the script is
  reading the wrong database, for example a custom `MONGO_DB`, `GOOGLE_MONGO_DB` or
  `GOOGLE_DATABASE_URL` that didn't reach the container. Dropping the old key then would make the
  real data unreadable. The report's `records` lists each target's count per store. If a store
  really is empty (for example, the stack never used the Google Forms integration), check that
  count, then run again with `--allow-empty`;
- the keyset file is not the deployed one (see above).

Otherwise it writes `keyset-rotation/final.keyset`, which holds the primary key only. The report
repeats the Typeform caveat (see "What the keyset encrypts"): the script cannot check that data.

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
  backup or from Typeform data. Give the services `rotated.keyset` again, run `reencrypt`, then
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
| 5 | `keyset.reencrypt` (`primary_id`) | moves every value to the primary: resumable, idempotent, compare-and-swap writes, each record read back before it is counted; `stores: auto` (the default) is every store the runner is configured for (`MONGO_URI`, `DATABASE_URL`, `GOOGLE_DATABASE_URL`), the primary first as the services' write mode says, and the primary's new ciphertext is copied to the other; refuses a published primary. Starting an apply run mails all admins (`settings.keyset_reencrypt` in the admin outbox: run id and primary key id); a dry run mails no one |
| 6 | `keyset.verify` | read-only full scan: every value opens; counts per key id (events `kid_<id>`) |
| 7 | `keyset.drop_old` | removes the other keys only when a full scan of EVERY target in EVERY store finds no value on them. It needs `MONGO_URI`, `DATABASE_URL` and `GOOGLE_DATABASE_URL` all configured (else `store_not_configured`), whatever the runner's own write mode says. The scan decrypts with the primary key ALONE, so a value the final keyset could not open also stops it (`values_not_readable`). Only the primary store (the services' write mode: give the runner the same `DB_WRITE_MODE`) must hold records |

`drop_old` has no target or store parameters on purpose, and a scan that did not finish (cancelled)
refuses. A Google credentials store that is empty because the integration was never used needs
`allow_empty_google` together with `google_in_use: false` (the combination `allow_empty_google` with
`google_in_use: true` is refused); the responses store is never accepted empty. It also refuses
while a Typeform integration instance reports a heartbeat (`typeform_reporting`). Values no candidate workspace
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

**Typeform.** The Typeform integration is a separate image that also receives the keyset from its
environment. It reports no heartbeat (if a build of it does, as service `typeform`, `drop_old`
refuses while it is seen) and what it stores can be neither checked nor re-encrypted
from here, so `promote`, `reencrypt` and `drop_old` need `typeform_acknowledged: true`: you confirm
you kept the old key for it or will reconnect its accounts after the final keyset.

**Where the new keyset is written.** The runner has no write privilege on the settings tables. It
seals and signs the new row itself (for the keyset's section only) and calls
`settings.task_write_keyset` (migration 0009), which accepts only this key, one version up, under
the writer lock, with a matching signed manifest and an audit row (`settings.task_set`, actor kind
`system`, the requesting admin in the detail) already in the same transaction. The same
transaction enqueues a `settings.keyset_changed` notification for all admins (setting name, action,
version and requester; never a value) in the admin outbox.

**Requirements and limits.** The keyset must be in the settings store (imported with the admin
import command) and the runner must be a reader of it. A keyset row imported before the runner
became a reader is hidden from the runner: the tasks refuse with `keyset_not_readable_by_runner`.
Its readers are part of the signed row, so only the admin service can fix it by re-writing the
row with the runner among its readers; do not edit the table. Stacks whose services still take the
keyset from the environment keep using the script above.

**Old keys are kept for backups.** `settings.history` keeps every version of the keyset, never pruned
(the history guard refuses deleting any row of a task-managed key, for the migration role and the
portal's writer alike). After `drop_old` the dropped key therefore stays recoverable from the
sealed history, so a database backup taken before the re-encryption can still be read: unseal the
older version with the settings master key. Purging old keys is a deliberate database operation by
the owner role (`ALTER TABLE settings.history DISABLE TRIGGER history_guard`, delete the versions,
re-enable it), best done only after the last backup that needs them has expired. `SETTINGS_MASTER_KEY`
must be kept as long as those backups are.

**Notices.** Every keyset write (`add_key`, `promote`, `drop_old`) and the start of a `reencrypt`
apply run enqueue one outbox row for all admins: setting name, tier, action, version, requester,
run id and the key ids or counts involved (never a key).
