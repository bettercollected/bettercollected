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

The platform admin metrics page (`/admin/metrics`, for the addresses in `PLATFORM_ADMIN_EMAILS`)
shows the same as a banner. Published keys are recognised by the SHA-256 of their key material
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
and its `__responses` / `__google` overrides. `--target` and `--store mongo|postgres|both` narrow
or override that. If the stack never ran the Google Forms integration, add
`--target responses` to `reencrypt` and `drop-old`.

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
- `records_unopenable`: no candidate context decrypts the record. Its workspace is unknown and
  none of its form's workspaces opens it, for example a response whose form was removed from every
  workspace. The ids are in the log. Such values stay under the old key. Either keep the old key
  (stop before step 5) or delete those records.

Repeat the dry run until it reports `values_stale` as 0 (or absent) for every target and store.

### 5. Drop the old key

```bash
rotate drop-old --keyset-file /rotation/rotated.keyset --out /rotation/final.keyset
```

This scans everything again and **refuses**, writing nothing, while any value still uses a key
other than the primary. The report shows the counts per key id. Otherwise it writes
`keyset-rotation/final.keyset`, which holds the primary key only.

### 6. Give every service the final keyset

As in step 3, with `keyset-rotation/final.keyset`. Then check that no service logs the
`MASTER_ENCRYPTION_KEYSET` warning and that the banner is gone from `/admin/metrics`.

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
