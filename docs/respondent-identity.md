# Respondent identity (anonymous responses)

A respondent who submits **without sharing their address** still has to find, and ask to delete, their own
submission. The response therefore keeps a one-way value derived from the signed-in address, and never the
address itself.

```
anonymous_identity = "v2:" + hex( HMAC-SHA256( key, md5_hex(email) ) )
```

- `md5_hex(email)` is exactly what `hash_string` (`backend/backend/app/utils/hash.py`) has always computed:
  the signed-in address (`user.sub`) as it is, no case folding or trimming. Values stored by 4.0 and earlier are
  that MD5, so they convert **without knowing the address**: `HMAC(key, stored_md5)` is the new value.
- `key` is `RESPONDENT_IDENTITY_KEY`, a dedicated secret. Anyone who knows an address can compute the MD5, but
  not the stored value; the linking protection is the key. It is never derived from `AUTH_AES_HEX_KEY` or the
  response keyset, and never logged.
- Code: `backend/backend/app/utils/respondent_identity.py` (derivation and matching),
  `backend/backend/identity_rekey.py` (the conversion pass).

## Where it is stored and compared

| What | Where |
|---|---|
| The response's identity | `app.form_responses` (`doc.anonymous_identity`, generated indexed column `anonymous_identity`); written by `WorkspaceFormService.submit_response` |
| The copy a deletion request keeps | `app.responses_deletion_requests` (same layout); copied from the response by `add_deletion_request` |
| Matching, "view / request deletion of my submission" | `FormResponseService` (two places) compare the stored value with the identity computed from the signed-in address |
| Matching, "my deletion requests" list | `PostgresFormResponseRepository.get_user_submissions` filters the deletion requests by the computed identity |

The public and API-key response formats do not carry it. A stored value that does not start with `v2:` is a
bug: matching refuses it (there is no MD5 fallback), and the conversion pass reports it.

## The key

- **Name:** `RESPONDENT_IDENTITY_KEY` (inventory section `auth_keys`, tier T4, read by the backend only).
- **Value:** at least 32 random bytes as hex or base64. Generate it once: `openssl rand -hex 32`. The exact
  rules define the key forever (the stored identities depend on its bytes), so they are fixed
  (`decode_identity_key`, `common/common/settings/secret_checks.py`):
  1. surrounding whitespace is ignored, nothing else is;
  2. text of only hex digits is **hex** (even length, either case) and is never read as base64: 64 digits are
     32 bytes;
  3. any other text is **base64**, standard (`+/`) or url-safe (`-_`) alphabet, padding optional;
  4. the decoded bytes are the key: at least 32, at least 16 distinct values, no repeated block, not a counting
     sequence, at least 4.0 bits of entropy per byte; base64 text must also mix at least two of lower case,
     upper case, digits and symbols (a lower-case passphrase that happens to decode is refused).
  Anything else (a short, repeating, patterned or placeholder value) is refused.
- **Where it is read:** the environment, else the settings store, like the other keys. In the compose stack
  `docker-compose.deployment.yml` passes it to the backend (empty means "read the store"); `bootstrap-keys`
  generates it into the store of a **new** stack. A stack that upgrades sets it once (root `.env` for compose, the
  stack definition for an orchestrated stack). Only the backend needs it: not the jobs worker, auth, the Google
  integration or the task runner.
- **Startup check:** the API refuses to start when it is missing, shorter than 32 bytes or low in variety
  (`require_identity_key`, first thing in the lifespan of `backend/backend/app/asgi.py`). The message names the
  setting and the command, never a value.
- **Wrong-key guard.** A mistyped key at the first 4.1 start would turn every stored MD5 into a value nobody can
  match, and later a key that differs between replicas (environment against store) would silently break matching.
  So before its first conversion the pass writes `app.respondent_identity_key_check` (one row, migration 0022):
  HMAC-SHA256(key, a fixed label). It is not the key and cannot match anyone. From then on a key whose check
  differs is refused: the API **does not start**, the command exits 4, and nothing is converted. No row but v2
  values already stored (an earlier run without the guard): the configured key is adopted and a warning is logged.
  The first 4 bytes of the check (8 hex digits) are logged by every pass and start as
  `key fingerprint=...`; write it down at the first start and pass it later as `--expect-fingerprint`.
- **Keep it.** The conversion cannot be undone, and a different key makes every stored identity unmatchable (the
  respondent can no longer find their anonymous submission). Back it up with the other keys; it is not part of
  the database backup.

## The one-time conversion

`python -m backend.identity_rekey [--dry-run] [--batch-size N] [--expect-fingerprint HEX]` converts every stored
identity, in both tables above. The API also runs it, **in the background after it has started** (matching refuses
a non-v2 value meanwhile, so a slow pass never delays serving or a healthcheck), and once more about five minutes
later for a 4.0 replica that was still writing MD5 while the roll finished. For a large `form_responses` table
(each conversion rewrites the response document) run the command before the roll instead.

- **Idempotent:** a value that already starts with `v2:` is never touched.
- **Resumable:** rows are visited in id order, one transaction per batch (default 500). The data is the
  checkpoint: a converted row no longer matches `NOT LIKE 'v2:%'`, so an interrupted run continues where it
  stopped. No checkpoint table. Both queries read only the partial indexes of migration 0022
  (`ix_form_responses_legacy_identity`, `ix_deletion_requests_legacy_identity`), so a start with nothing left to
  convert does not walk the tables. The migration is expand-only and needs no key.
- **Safe beside live traffic and replicas:** only the one `anonymous_identity` key of the document is rewritten
  (`jsonb_set`), and only while the row still holds the value that was read; a row changed meanwhile is counted
  and left. One process runs the pass at a time (a Postgres advisory lock, released with its connection even when
  the unlock fails); the others skip it.
- **Counts only:** logs and output hold counts per table (`converted`, `changed_meanwhile`, `remaining`) and the
  key fingerprint, never an id, a value, a hash or a check value. A failure in the API is logged by its exception
  class and never stops it. The `remaining` counts of every pass, including the delayed one, are in the log line
  `respondent identity pass: key fingerprint=... converted=... remaining=...` (not on the admin Health page).
- **Exit status** of the command: 0 nothing left to convert, 1 values remain or the run failed (a `--dry-run`
  that finds values also exits 1), 2 another process holds the lock, 3 the key is missing or unusable, 4 the key
  is not the one that converted the stored identities (or not `--expect-fingerprint`).

Why not an admin task or the `backend.migrate` import CLI: the task runner would need the secret (it is
deliberately a separate, least-privilege service), and `backend.migrate` is the 4.0 import tooling that goes away
with Mongo. The pass belongs to the service that computes the identity.

## Upgrading to 4.1

1. Before the 4.1 roll: generate the key (`openssl rand -hex 32`) and keep it with the other secrets. Never put
   it in a ticket, a chat or the repository.
2. Add `RESPONDENT_IDENTITY_KEY` to the **backend** service of the 4.1 stack (compose: the root `.env`;
   orchestrated stack: its environment). 4.0.x ignores it.
   For a large table, run `python -m backend.identity_rekey --dry-run` and then the command itself in a one-off
   container of the 4.1 image before the roll, and note the `key fingerprint`.
3. Roll the backend to 4.1. The first replica converts in the background under the lock (the log line is
   `respondent identity pass: key fingerprint=... converted={...} changed_meanwhile={...} remaining={...}`).
   Compare the fingerprint with the one you noted; a replica whose key differs from the stored check does not start.
4. **Submit an anonymous response with your own account and confirm you can view it** (and see it in your
   deletion requests after asking for deletion on a test response). This proves the key in use is the one the
   stored identities were converted with.
5. When no 4.0 backend replica is left, run the pass once more (the API does so by itself about five minutes
   after each start; or `python -m backend.identity_rekey --expect-fingerprint <fingerprint>` in a one-off
   container with the same environment): a 4.0 replica still running during the roll can store one more legacy
   value. Done when the command exits 0 and `remaining` is 0 in both tables.
6. Rolling back to 4.0.x afterwards: 4.0 compares the MD5, so respondents cannot find or delete their
   anonymous submissions while 4.0 runs. Nothing is lost; the 4.1 start converts whatever 4.0 stored in the
   meantime.

## Key rotation (documented, no tooling)

`HMAC(new, md5_hex)` cannot be computed from `HMAC(old, md5_hex)`, and the MD5 is not stored, so a rotation is not
a re-key of the stored values. It works by keeping the old key as a match fallback, upgrading a value to the new
key when it matches under the old one, and retiring the old key once no stored value is left on it. That fallback
is not built in 4.1; until it is, treat the key as permanent.
