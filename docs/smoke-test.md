# Production smoke test

`scripts/smoke/` checks a running instance end to end: a browser (Playwright,
Chromium) for what respondents do, and the public REST API with a scoped key
for what staff do. It runs in GitHub Actions
(`.github/workflows/smoke-production.yml`) against one **dedicated test
workspace** in production, with secrets from the protected `production-smoke`
environment. Nobody running it, people or agents, sees those secrets; the run
only reports pass/fail, timings and ids from the test workspace.

## What it checks

| # | Check | How |
|---|---|---|
| 7 | Public endpoints answer | The web app's home page and `/api/config`, the API's `/providers`, the public API's OpenAPI document and the workspace lookup by name or id. Runs first; nothing else runs when it fails. |
| 3 | Standing responses export and decrypt | Reads every response of the standing form through the public API (`responses:read`, the export scope) and compares each answer with the values it was given. A response that no longer decrypts reads as empty and fails the check: the canary for the keys and the response codec across releases. |
| 1 | Sign-in with an emailed code | A new respondent account per run: the browser asks for a code for `<mailbox>+<run tag>@…` on the workspace's sign-in page, the suite reads the newest code mail to exactly that address and enters the code. Asked for once, never again in the same run. |
| 2 | Create, publish, submit, read back | Creates a one-question form from a form spec document, publishes it, answers it in the browser as the signed-in respondent (sharing their email), and reads the response back through the API. |
| 5 | Form on the custom domain | Opens that form at `https://<custom domain>/forms/<slug>` and waits for its title. |
| 4 | Deletion request | The respondent asks for the response's deletion on the portal's submission page; staff (the API key) see it pending and decline it with a fixed reason; the respondent's deletion requests page and data then say "Not deleted: …", never "Deleted". |
| 6 | Google Forms | Reads the import mode from `/providers`. In `readonly` (from 4.1): the previously imported test form and its responses read back, and a new import is refused with the read-only message. In `on`: the imported test form reads back; the import itself is skipped (see [Limits](#limits)). Skipped when the instance offers no Google Forms. |

Stripe is not part of it.

### What it creates, keeps and deletes

- **Kept:** the standing set, one form titled "Smoke test standing set (keep,
  do not edit)" with six question types and three responses. The first run
  creates it; later runs only read it. Do not edit it or answer it by hand:
  its answers are compared value by value. To start over, delete the form;
  the next run makes a new one.
- **Deleted at the end of every run, pass or fail:** the run's form (with its
  response and the deletion request), the run's respondent account (through
  the product's account deletion, which finishes in the background) and the
  run's code mail (where the mailbox access allows deleting).

### Safety rules it follows

- Staff actions use the API key only: it works in the test workspace and
  nowhere else. Before anything is written beyond the standing form, the
  suite checks that the key's workspace is the one in `SMOKE_WORKSPACE_ID`
  and stops otherwise. No platform-admin rights, no admin portal.
- The browser is a respondent of the test workspace, nothing more.
- Mailbox: read-only, and only mails addressed to this run's plus-address.
  Afterwards those mails are moved to the bin (IMAP); the Gmail API with
  `gmail.readonly` cannot delete, so they stay.
- One code per run, one run at a time (`concurrency`), no retries of a failed
  step or run; an API 429 is waited out once if its `Retry-After` is short.
- The report holds pass/fail, timings and test-workspace ids. Codes, tokens,
  cookies, addresses and mail contents are removed from every line written
  (`smoke/redact.py`; the self-test proves it). No screenshots, traces or
  videos are recorded.

## Configuration

Everything comes from the `production-smoke` environment.

**Secrets**

| Name | What |
|---|---|
| `SMOKE_API_KEY` | API key of the test workspace with the scopes `forms:read`, `forms:write`, `responses:read` (with its acknowledgement), `deletion_requests:read` and `deletion_requests:write` |
| `SMOKE_IMAP_APP_PASSWORD` | Gmail app password for IMAP, **or instead** the three below |
| `SMOKE_GMAIL_CLIENT_ID`, `SMOKE_GMAIL_CLIENT_SECRET`, `SMOKE_GMAIL_REFRESH_TOKEN` | Gmail API access with the `gmail.readonly` scope |

Exactly one mailbox set: with both, or neither, or an incomplete Gmail set, the
run stops with a message that names what is wrong.

**Variables**

| Name | What |
|---|---|
| `SMOKE_APP_URL` | The web app, e.g. `https://admin.example.com`. The API is `<app>/api/v1` when that answers, otherwise the address the app itself calls. |
| `SMOKE_MAILBOX` | The test mailbox's base address (`name@gmail.com`); each run uses `name+smoke-<run>-<attempt>-<random>@gmail.com` |
| `SMOKE_WORKSPACE_ID` | The test workspace's id or name (handle) |
| `SMOKE_CUSTOM_DOMAIN` | The test custom domain, a host name without `https://` |
| `SMOKE_GOOGLE_FORM_ID` | The test Google Form's edit id (from `/forms/d/<id>/edit`) |

The key's creator must be an owner or admin of the test workspace: a key never
does more than its creator may, and the suite needs `form.edit`,
`form.delete`, `response.read`, `response.export` and `privacy.manage`.

## Owner setup (once)

All of this is done by the owner, never by an agent, and no value is ever
pasted into an issue, a pull request or a chat.

1. **Mailbox and Google account.** One company-owned Gmail account serves as
   the test mailbox and as the Google account for the import.
   - Plus-addressing needs no setup in Gmail. Add a filter: from the
     instance's sender address, "Never send it to Spam".
   - Choose one way for the suite to read codes:
     - **IMAP:** turn on 2-step verification, create an app password
       ("Mail"), and store it as `SMOKE_IMAP_APP_PASSWORD`. IMAP access must be
       on in Gmail's settings.
     - **Gmail API:** in a Google Cloud project of the company, enable the
       Gmail API, configure the OAuth consent screen (internal, or external
       *published*: a refresh token of an app left in "Testing" stops working
       after 7 days), create an OAuth client, and authorise it once for the
       test account with only the `https://www.googleapis.com/auth/gmail.readonly`
       scope. Store the client id, the client secret and the refresh token.
2. **Test account and workspace in production.** Sign up with the mailbox's
   base address. Its workspace is the test workspace; give it a plan that
   allows custom domains. Note its name (or id) for `SMOKE_WORKSPACE_ID`.
3. **API key.** In the test workspace, as its owner: dashboard → AI → MCP →
   new key, with the five scopes above and the acknowledgement for
   `responses:read`. Store it as `SMOKE_API_KEY`.
4. **Test Google Form.** In the Google account, make a small form and answer
   it a few times. In the test workspace, connect the Google account once by
   hand on the normal import screen (Google blocks automated sign-ins) and
   import that form. Store its edit id as `SMOKE_GOOGLE_FORM_ID`.
5. **Test custom domain.** Point one DNS record for a subdomain at the forms
   edge, add the domain in the test workspace's settings and wait until it is
   verified. Store the host as `SMOKE_CUSTOM_DOMAIN`.
6. **GitHub environment `production-smoke`.** Repository settings →
   Environments → new environment:
   - Deployment branches and tags: selected branches only, `develop` and
     `release/**`. A pull request's branch can then never run with these
     secrets.
   - Required reviewers: the owner (every run waits for that approval).
   - Add the secrets and variables above.

## Running it

Actions → **Production smoke test** → Run workflow, on `develop` or a
`release/**` branch; optionally say what it is for. The run waits for the
owner's approval of the environment, then takes a few minutes.

- The run's summary page shows the result table, ready to paste on a release
  issue. The same table and a `report.json` are in the run's artifact
  `smoke-report-<run>-<attempt>` (kept 30 days).
- Exit status: everything passed or was skipped; a failed check fails the
  run; an incomplete configuration fails it with the reason.
- A failed run is not retried automatically. Look at the failed check's note,
  fix the cause, then start a new run (each run asks for one sign-in code).

**Schedule.** The workflow's `schedule` is commented out. To turn it on,
uncomment it (monthly by default): a monthly run also keeps the stored Google
connection in use, which otherwise expires after about six months idle.
Scheduled runs wait for the same approval.

## Rotating the secrets

Rotate after anyone who could read them leaves, when a value may have leaked,
and at least yearly. Each one can be replaced without a code change:

- **API key:** create a new key with the same scopes (step 3), replace
  `SMOKE_API_KEY`, then revoke the old key in the same tab. Its calls stop at
  once.
- **App password:** create a new app password, replace
  `SMOKE_IMAP_APP_PASSWORD`, then revoke the old one in the Google account's
  security settings.
- **Gmail API:** create a new client secret (or a new OAuth client),
  authorise once more for a new refresh token, replace the three secrets,
  then delete the old secret or client and remove the old grant under the
  Google account's third-party access.
- **Switching mailbox access** (IMAP to the Gmail API or back): add the new
  set and delete the old one in the same change; a run with both sets refuses
  to start.
- **Test account:** to replace it, create the new workspace and key, update
  `SMOKE_WORKSPACE_ID` and `SMOKE_API_KEY` together, and delete the old
  workspace. The first run makes a new standing set.

If a value leaked: revoke it first (key, app password or OAuth grant), then
replace it.

## Limits

- **Google import while the mode is `on`:** the import runs with the stored
  Google connection of the account that connected it, so it needs a signed-in
  session of that account. The suite signs in only a new respondent per run
  (and the product matches email addresses exactly, so a plus-address is a
  different account). Testing the import itself would need the suite to sign
  in as the test account as well (a second code per run, and a full staff
  session), or an API-key way to import. Until the owner decides, that part
  is reported as skipped; from 4.1 (`readonly`) there is no import to test.
- The account deletion of the run's respondent finishes in the background;
  the report says that it was requested.

## Developing the suite

The self-test runs in CI whenever `scripts/smoke/` changes: configuration,
code-mail matching (with a fixture mail), the report's redaction and the
standing-set comparison. No secrets, browser or network.

```bash
cd scripts/smoke
uv sync
uv run pytest
```

**Dry run.** `.github/workflows/smoke-dry-run.yml` runs the whole suite
against a throwaway stack it builds itself (Postgres, auth, backend, web app
and a Mailpit inbox for the codes): by hand, and on pull requests that change
the suite. It is not part of `CI ok`. The Google Forms check is skipped there
(no provider) and the run account's deletion stays queued (no worker).

The same against a stack on your machine, never against production (the codes
come from the stack's Mailpit; no mailbox secret may be set):

```bash
cd scripts/smoke
uv run playwright install chromium
# the owner signs in by code and gets a key (writes a mode-600 env file)
uv run python -m smoke.devstack --api http://localhost:8000/api/v1 \
  --mailpit http://localhost:8025 --origin http://localhost:3000 --env-file .dry-run.env
set -a; . ./.dry-run.env; set +a
SMOKE_APP_URL=http://localhost:3000 SMOKE_MAILBOX=smoke@example.com \
SMOKE_CUSTOM_DOMAIN=127.0.0.1:3000 SMOKE_GOOGLE_FORM_ID=<any edit id> \
uv run python -m smoke --api-url http://localhost:8000/api/v1 \
  --mailpit http://localhost:8025 --debug-dir /tmp/smoke-debug
rm .dry-run.env
```

For check 5, give the local workspace the custom domain `127.0.0.1:3000`
(the dry-run workflow sets it in the database). `--debug-dir` writes the page
structure (redacted) of a browser step that failed.
