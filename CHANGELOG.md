# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [RELEASING.md](RELEASING.md) for how releases are cut.

> This file was introduced partway through the project's life, so history before
> `2.2.0` is captured by git tags and release notes rather than here. The sections
> for `2.3.0` to `3.4.0` were assembled afterwards from the tags and the merged
> changes between them.

## [Unreleased]

### Added

### Changed

### Removed

### Fixed

### Security

## [4.0.0] - 2026-10-19

4.0.0 moves platform administration out of the public app into an internal admin
portal, and moves the stack's keys and settings into a signed, encrypted settings
store. A `deploy.sh` install now needs one value from you (`PLATFORM_ADMIN_EMAILS`).
The release also adds a public REST API with clients for forms as code, calculated
fields, answer rules and multiple endings in the builder, outline-first AI form
generation with proposals you accept or reject, new form looks (Kantlijn, Raster,
Leaflet), a form language setting and organisation logos, and a long list of
hardening changes to the deployment files and the internal APIs.

**Upgrading from 3.x: read [Upgrading to 4.0](docs/admin-service.md#upgrading-to-40)
first, and back up before you start.** The changes that need your attention:

- `deploy.sh` imports the keys and settings your files hold into the settings store.
  `SETTINGS_MASTER_KEY` (generated once into the root `.env`) is now required by every
  service that reads the store: back it up, it cannot be recovered. `SETTINGS_STORE=off`
  is the rollback.
- The shipped signing and encryption keys are gone. Published `AUTH_JWT_SECRET` and
  `AUTH_AES_HEX_KEY` values are replaced (everyone is signed out once, Google
  connections and form-action secrets need re-entering), and a weak or malformed legacy
  secret is refused on import until you replace it.
- Behind a reverse proxy or load balancer, set `TRUSTED_PROXIES`.
- `DEBUG` and the internal APIs' `/docs` are off unless you turn them on.
- The public app's `/admin/metrics` page is gone; the metrics live in the admin portal,
  which you reach through an SSH tunnel and never through a proxy.
- `GET .../forms/{form_id}/all-submissions` needs the export permission.
- Temporal's host port 7234 is no longer published; Umami's dashboard moved to
  `127.0.0.1:3004` and its built-in login is replaced.
- The webapp, the Temporal worker and the Typeform service read their own env files
  (`.env.webapp`, `.env.worker`, `.env.typeform`) instead of `.env.deployment`.
- The deploy workflow deploys release tags (`vX.Y.Z`) only.
- Database migrations: application schema `0013` to `0016`, the new admin schema chain
  (`0001` to `0017`); the roles script runs before and after them.

### Added

- **Internal admin portal.** A separate service (`python -m backend.admin.serve`),
  published on the host's loopback only (`127.0.0.1:8100`) and reached through an SSH
  tunnel. Every request passes a host and address gate; sign-in is a mailed code plus an
  authenticator code (TOTP), with single-use recovery codes, fresh-code confirmation for
  sensitive actions, sessions bound to address and browser, CSRF and same-origin checks,
  and a strict content security policy. Every sign-in, change and refusal goes to an
  append-only, hash-chained audit log. Pages: health (services, schemas, integrity),
  configuration (every setting with its source, secrets never shown), platform metrics
  (counts only), audit log, sessions, **settings** (edit, clear, restore, history, integrity
  check) and **tasks** (start, cancel, resume, history and live progress). Background loops
  mail the admins about changes, remove old rows and check the store's integrity. The
  portal follows the interface's design system. Details: `docs/admin-service.md`.
- **First-run setup wizard.** A fresh install can be set up without any mail working:
  the host prints a one-time token (`setup-token`, valid 60 minutes, shown on the console
  only and stored hashed), the operator redeems it at `/setup`, enrols an authenticator,
  optionally saves the admin sign-in mail settings after a delivered test mail, and notes
  the master key fingerprint. The wizard exists only while no admin has a second factor
  and a valid token waits, and closes for good when finished.
- **Settings store.** A signed (and, for secrets, encrypted) store with a registry of
  every setting, versions and history, a loader that services read through with a signed
  disk snapshot and hot reload, and an inventory of all settings
  (`docs/settings-inventory.md`). The backend, jobs worker, auth and the Google
  integration read their settings from it (`SETTINGS_STORE=required` in the deployment).
- **Host commands for the settings store.** `python -m backend.admin` gains `bootstrap-keys` (generates a fresh
  install's own keys into the store without printing them), `settings-import
  --from-compose-config [--dry-run]` (imports the compose configuration once, reporting
  conflicts between services instead of choosing), `settings-drift`, `settings-prune`
  (removes the settings the store already holds from env files, so a stale environment
  value cannot override the store), `settings-env-export`, `settings-set`,
  `settings-restore`, `settings-history`, `settings-verify`, `setup-token`,
  `master-key-fingerprint` and `settings-mail-apply` (and, for the portal's sign-in,
  `reset-factor`, `unlock`, `resume-sign-in`, `revoke-sessions` and `audit-verify`);
  `deploy.sh` runs the settings ones in a one-off container under the same names.
  Every change is audited. The
  admin sign-in mail has its own `admin_mail` settings section, which can only be saved
  after a test mail was delivered.
- **Task runner.** A separate service with its own narrow database roles runs the tasks
  the portal lists: read-only checks (`responses.check_undecryptable`), a backfill that
  stamps responses and deletion requests with their workspace
  (`responses.backfill_workspaces`) and the response keyset rotation (`keyset.add_key`,
  `keyset.promote`, `keyset.reencrypt`, `keyset.verify`, `keyset.drop_old`). Dry runs come
  first, runs are signed, resumable and cancellable.
- **Public REST API for forms as code**, at `/api/v1/public/v1` with workspace API keys:
  list, create from a whole spec document, read as a document with an ETag, replace
  (`If-Match` required), replace preview, validate, publish, edit operations, and response
  summaries. It has a per-key rate limit, `Idempotency-Key` on create, operations and
  publish, and one error shape. The OpenAPI document is committed in `docs/api`. A
  TypeScript client and a Python client with a `bettercollected` command (`pull`, `diff`,
  `push`, `validate`) live in `sdk/` (not published to a package registry).
- **Form spec v1**: the public document shape of a form (pages, fields, logic, jumps,
  endings, theme, hidden fields, logo and trust settings) as a versioned JSON Schema in
  `docs/spec`, with id-addressed edit operations (client refs, atomic batches), size
  limits, and the operations' own JSON Schema. The AI, the MCP server and the public API
  share them.
- **Answer rules and calculated fields.** A question's validations (length, format,
  value, number of choices, with presets such as Dutch postcode, IBAN and phone number)
  are now enforced for respondents and on the server. Calculated fields compute a value
  from earlier answers with a formula (expressions v1), can be shown or hidden from
  respondents and used in logic and piping; the server recomputes them and never trusts
  the browser's result.
- **Multiple endings.** A form can have several endings, one of them the default; a jump
  can choose the ending to show, the submission records the ending reached, and the flow
  view shows each ending as a node.
- **AI form generation starts from an outline.** The AI proposes an outline you review
  and edit before the form is built; the model fills only what is missing, and quality
  checks run on generated and edited forms. In the chat, proposals can be accepted or
  rejected (all or chosen changes) instead of being applied at once. The AI keeps a form
  in one language, can change a form's look by preset, name a page's section and set the
  form's language.
- **Form language.** A form declares the language its questions are written in
  (Nederlands, English, Deutsch, Français, Español, Italiano, Português, Polski, Dansk,
  Svenska, Norsk bokmål, Suomi), set under Form → Language in the builder, by the edit
  operation `set_form_language` (AI chat, MCP, public API) or by `language` in the form
  spec. Respondent pages mark the form's text with it for screen readers and browsers,
  and it goes live with the next publish. Forms generated from an outline get the
  outline's language.
- **Theme presets and theme shape.** Complete-look presets **Kantlijn** (a small-press
  book: Besley titles, a cloth-green cover beside a marbled endpaper, a rose margin rule
  and notes) and **Raster** (a Swiss poster: expanded Archivo titles on a visible column
  grid, square edges, outlined buttons, the submission number as the ending's headline),
  and the **Leaflet** style and preset (each page a numbered section, like a plain-language
  information leaflet; new forms start with it). A form theme can also set its title, text
  and data faces (Public Sans, Atkinson Hyperlegible Next, Archivo, Besley, Rubik, Atkinson
  Hyperlegible Mono; self-hosted, loaded only by a form that uses them),
  wide titles, the corners of fields, options and buttons (sharp, soft, round), the button
  style (filled, outlined, pill) and a highlight colour for the chosen answer, plus the
  `columns` and `margin` background patterns and built-in `marble` artwork served by the
  app itself. Every key is optional: stored forms and the existing presets render as
  before. The builder's Design tab and the Themes page edit them.
- **Organisation logo on every respondent page.** Upload, replace or remove a form's logo
  (PNG, JPEG or WebP, at most 1 MB and 3000 px per side, checked and re-encoded, stored in
  your own storage), choose its position and alternative text, or use the workspace logo.
- **First-party images.** Photos from Unsplash are served through your own server and
  cached once in your storage, and an image address pasted into a form is copied into your
  storage, so respondents' browsers contact no third-party image host. Only first-party
  addresses are accepted when forms and themes are saved.
- **Builder.** A form outline in the left panel, an inspector with breadcrumb, answer
  rules and numbering, a searchable insert menu with canvas insert commands and keyboard
  authoring, question numbers shown to respondents, and a form document store with undo
  and redo per action (one step per action and per run of typing, with Undo offered after
  deleting a question or page). Publishing is held for untitled questions. A save based on
  an older draft is refused instead of overwriting newer work.
- **Respondent forms and portal in Dutch and English** (texts, the submission-number
  search, the portal's tabs and form search, the feedback view), clearer states and touch
  targets for form controls, and a shared reading order and landmarks.
- Emails use the Sireto design tokens, a system font stack and the Sireto footer.

### Changed

- **`deploy.sh` needs one value from you and keeps the stack's keys in the settings
  store.** A new install generates `SETTINGS_MASTER_KEY`, the database passwords and the
  Umami secret into the root `.env`, creates the stack's own keys (`AUTH_JWT_SECRET`,
  `AUTH_AES_HEX_KEY`, `AUTH_INTERNAL_NOTIFY_KEY`, `TEMPORAL_API_KEY`, the response keyset)
  straight into the settings store before any service starts (nothing is printed), and
  shows a one-time setup token on the console. An upgrade imports what your files hold
  (never overwriting) and compares it with the store. The Temporal worker stays off the
  store with two keys in its environment (`API_KEY`, `AES_HEX_KEY`) and never gets the
  master key. `DEBUG` and `API_DOCS_ENABLED` are no longer pinned in the compose file (a
  pinned value would win over the portal); both stay off by default.
  **Upgrade note:** re-run `deploy.sh`, then, once the stack runs well,
  `./deploy.sh settings-prune` (an environment value still wins over the store until
  you do). See "Upgrading to 4.0" in `docs/admin-service.md`. Back up
  `SETTINGS_MASTER_KEY`: without it the store cannot be read.
- **`GET /workspaces/{id}/forms/{form_id}/all-submissions` needs `response.export`,** like
  `.../all-submissions/export`. It returns every response of a form decrypted and
  unpaginated, but used to ask only for `response.read`; it now asks for the export
  permission like the export route. Owners, Admins and Editors are unaffected; Viewers,
  Reviewers and Privacy officers are refused. The builder's flow view no longer
  needs the answers: it reads the new `.../submission-paths` (`response.read`), which
  returns each submission's pages, jumps taken and ending reached, and no answer values,
  identities, response ids or dates.
  **Upgrade note:** API clients and scripts that called `.../all-submissions` with a
  read-only role need the export permission, or should use the paths route if they only
  need traffic counts.
- **Flow events are limited per /64 for IPv6** (IPv4 stays per address) and **deleted after
  13 months** (`API_FLOW_EVENTS_RETENTION_DAYS`, default 395, 0 keeps them): a MongoDB TTL
  index on `created_at`, and for PostgreSQL a sweep on the write path. Flow events are
  accepted only for published forms' pages and are rate limited per client, also behind
  Cloudflare.
- **The webapp adopts the Sireto design system** (see `DESIGN.md`): one blue ramp around
  Sireto blue `#123FC9` with a `#1649E2` primary button face, one neutral ramp, Instrument
  Sans and JetBrains Mono self-hosted through `next/font` (no page contacts Google's font
  servers, and `next build` no longer downloads fonts), a 6px radius, hairlines instead of
  decorative shadows, a 2px Sireto-blue focus outline on every interactive element, the
  "key edge" on buttons, and mono type for IDs, slugs, URLs and keys. Tailwind CSS is now
  version 4. The Default form theme is retuned (`#1649E2` / `#101828` / `#F5F7FB`) and
  the backend's Default theme for AI-created forms uses the same values; forms keep the
  theme colours stored on them. Public and auth pages carry the Sireto trademark line.
  **Respondent forms** keep Public Sans, their radii and button shapes; in every theme
  field borders are more visible (the theme's border colour at 3:1 or more), the focus
  outline wears the theme's action colour and the "Back" link uses the theme's ink.
- **AI insights analyse only responses whose page showed the AI notice,** and the notice
  appears in the privacy strip of the form; AI edits never add the notice stamp.
- **Mail.** Sign-in codes no longer fail silently, mails are sent in the product's name
  instead of a workspace's, and avatars load only from known hosts.
- **PDF import** limits refuse a start that would wait too long, a failed import says why
  (in English and Dutch) and leaves no empty draft, and an import whose job died is
  expired as interrupted and frees its slot.
- The flow view's insights count submission paths, not answers; the required star follows
  the question title; dialogs have labelled close buttons, opaque surfaces and one
  stacking scale.

### Removed

- **The public app's platform metrics dashboard is gone.** The webapp no longer serves
  `/admin/metrics` (page, "Platform metrics" menu entry and client) and the backend and
  auth services no longer serve `GET /admin/metrics`.
  **Upgrade note:** the platform metrics dashboard now lives in the internal admin portal
  (reachable from the host only, behind a second factor). `PLATFORM_ADMIN_EMAILS` also
  lists the portal's super admins, so keep it set. The `ADMIN` role it grants after a
  verified sign-in, and the operator-only endpoints that check it (coupons, actions,
  plugin providers, user tags, `GET /persistence/status`), are unchanged.
- The broken `export-csv` route; the CSV download uses `.../all-submissions/export`.
- The unused `GOOGLE_AES_KEY` setting.

### Fixed

- Builder: edits are never lost or published stale; leaving the editor never saves an
  emptied builder; the title editor saves its last keystrokes; the canvas toolbar acts on
  the question by id; deleting an ending or an outline question is one undo step.
- Respondent forms: a required question needs an answer with a value; typing that ends
  where it started leaves no undo step; the date picker shows only the month's days, its
  month arrows work and its text reads at 4.5:1 in every theme; the question page header
  is opaque over patterned pages; the privacy panel opens by default only when Start stays
  in view; only http(s) links open from the ending page's button; the share-my-email
  checkbox shows when it is checked; a page that is invalid scrolls to the question only
  where the page can scroll; videos load from YouTube or Vimeo only when the respondent
  presses play.
- A form's declared language survives undo, partial saves and bare reads and reaches the
  builder and the respondent page; new forms and copies answer with their language.
- A form saved at the same moment as another no longer loses the second save; a
  duplicated form's images are checked like a template copy; a page's question numbering
  is kept on save.
- Responses are written to a workspace's own copy by id, and scoped to the workspace they
  belong to.
- Action secrets and configuration are kept out of every response, and changing one
  action's credentials keeps the other actions' secrets.
- Local development: `API_PUBLIC_URL` unset no longer stops the stack from starting; the
  dev compose files bind every port to the loopback.

### Security

- **Deployment hardening.** The public webapp, the Temporal worker (which drives a browser
  on user-supplied URLs) and the Typeform service no longer receive the contents of
  `.env.deployment`; each reads an env file of its own (`.env.webapp`, `.env.worker`,
  `.env.typeform`) that `deploy.sh` creates once from the lines it reads. `deploy.sh` now
  starts the admin service, jobs worker, document sandbox and task runner, shows the setup
  token only once the admin service is healthy, keeps all generated and exported files
  owner-only, refuses a stack found under another compose project name instead of giving
  it new passwords, and decides the Mongo half of "does this stack hold data" itself.
  First-party services run with `no-new-privileges`, and the webapp, worker and Typeform
  service drop all capabilities. The Mongo seed no longer creates a `seeduser` account
  (and removes it from existing volumes) and passes no password on a command line.
  `OAUTHLIB_INSECURE_TRANSPORT` is no longer set in the shipped `.env.deployment`. The
  deploy workflow pins its actions by commit and deploys release tags (`vX.Y.Z`) only.
  **Not changed:** the Temporal worker still starts Chromium with `--no-sandbox` as root;
  it holds no secrets and drops all capabilities.
- **Temporal is no longer published on the host, and Umami's built-in login is replaced.**
  `docker-compose.deployment.yml` published Temporal's unauthenticated frontend on host
  port 7234; it is reachable on the compose network only now (`docker compose exec
  temporal temporal ...` from the host). Umami's admin login was the well-known
  `admin`/`umami` on a port the respondents' browsers have to reach: its dashboard is now
  published on `127.0.0.1:3004` only, port `3003` is nginx and serves the tracker only,
  and `deploy.sh` replaces the built-in login with a generated password after the first
  start (and on an upgrade when the built-in login still works), stored as the
  `UMAMI_PASSWORD` setting. The Temporal, Umami and Mongo databases take generated
  passwords on a new volume (the `MONGO_URI` setting is stored to match); a volume created
  by an earlier release keeps its password. The remaining internal-only credentials and
  ports are listed in `docs/admin-service.md`.
  **Upgrade note:** anything that used port 7234 must join the compose network; a reverse
  proxy that pointed at 3003 for the Umami dashboard must point at 3004. To sign in to
  Umami yourself: `./deploy.sh settings-env-export --keys UMAMI_USERNAME,UMAMI_PASSWORD
  --out FILE`.
- **Admin portal sign-in and store hardening.** Wrong email codes no longer lock the
  genuine admin out (they count per email and address; the second factor keeps its own
  lock), a flood against one sign-in cookie costs no database work and no audit rows, and
  the code-request limits no longer collapse into one bucket behind the Docker gateway
  address (which also logs a startup warning). Replacing the authenticator and making new
  recovery codes need a fresh code in the request, and new recovery codes mail every
  admin. The setup token cannot be burned by a flood, and a saved mail password is pinned
  to its TLS settings. Responses add HSTS (over TLS) and a deny-all `Permissions-Policy`.
  The portal's database roles are narrow (the admin role cannot read application data
  except through two functions that return counts; the task runner has its own roles per
  owning schema), and the integrity loop checks the audit chain incrementally.
- **The settings store checks key material when it is written.** Weak or malformed
  `AUTH_JWT_SECRET`, `AUTH_INTERNAL_NOTIFY_KEY`, `TEMPORAL_API_KEY`, `AUTH_AES_HEX_KEY`,
  `MASTER_ENCRYPTION_KEYSET` and custom-domain keys are refused on `settings-set`,
  `settings-import`, `bootstrap-keys` and in the portal. **Upgrade note:** a legacy short
  or low-entropy `AUTH_JWT_SECRET` is refused on import; replace it (everyone is signed
  out once) and import again. With `SETTINGS_STORE=required` a service refuses to start on
  a store older than its own snapshot, and the admin integrity check flags a store behind
  what running services report. The actions executor is no longer listed as a reader of
  the Fernet and internal API keys.
- **No more shipped signing and encryption keys.** `.env.deployment` used to contain
  concrete values for `AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY` (a Fernet key) and
  `MASTER_ENCRYPTION_KEYSET`; anyone could use them to forge session tokens and to decrypt
  or forge Fernet-encrypted data (OAuth and SSO state, form-action secrets, SCIM webhook
  secrets, Google credentials). They are gone from the file. `deploy.sh` generates its own
  and the services refuse to start when `AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY`
  (`AES_HEX_KEY` in the workers) is empty, not a valid Fernet key, or any value that was
  ever published in this repository; the error says what to set.
  **Upgrade, every stack must set its own values:**
  - With `deploy.sh`: re-run it. Values you set yourself in `.env.deployment` are copied
    into the root `.env` and kept; the published ones are replaced with new random values.
  - Rotating `AUTH_JWT_SECRET` signs everyone out once.
  - Data encrypted with the old `AUTH_AES_HEX_KEY` can no longer be read: reconnect Google
    Forms and Google Sheets, re-enter form-action secrets and regenerate SCIM webhook
    secrets. In-progress SSO and OAuth sign-ins restart.
  - Responses are encrypted with `MASTER_ENCRYPTION_KEYSET`, so a stack that already holds
    responses must keep the keyset it has used: `deploy.sh` stops and asks for it instead
    of generating a new one. Copy the `MASTER_ENCRYPTION_KEYSET` line from your previous
    `.env.deployment` into the root `.env`. That keyset was public too: anyone with access
    to the database could read those responses, so rotate it
    (`docs/response-keyset-rotation.md`).
  - Without `deploy.sh`: set your own `AUTH_JWT_SECRET` (`openssl rand -hex 32`) and
    `AUTH_AES_HEX_KEY` (a Fernet key) on the backend, jobs worker, auth and integrations,
    the same Fernet key as `AES_HEX_KEY` on the Temporal worker and the actions-executor,
    and keep your `MASTER_ENCRYPTION_KEYSET`. See `docs/DEVELOPERS_GUIDE.md`.
- **A published response encryption keyset is flagged, and can be rotated without losing
  data.** Every service that loads `MASTER_ENCRYPTION_KEYSET` logs a warning at startup
  when it holds a key that was published in this repository, naming the variable only.
  The keyset is not refused, because a new one could not read the stored responses.
  Instead the rotation (the admin tasks, or `python -m scripts.rotate_response_keyset`)
  adds a new AES-256-GCM primary key, re-encrypts answers, hidden fields, internal
  answers, feedback messages and Google credentials in batches (idempotent, resumable,
  with a dry run), and only then drops the old key, refusing while any value still uses
  it. Runbook, with the order across services, backups and rollback:
  `docs/response-keyset-rotation.md`.
- **The internal APIs no longer serve API docs by default, and 422 answers no longer echo
  the rejected input.** The backend, auth and Google services served `/docs`, `/redoc` and
  `/openapi.json` on their public path. They now serve them only when
  `API_DOCS_ENABLED=true` (off by default; the `.env.example` files turn it on for local
  development, and neither `.env.deployment` nor `docker-compose.deployment.yml` sets it).
  The public REST API's `/openapi.json` is unchanged. Request validation errors keep their
  `detail` list of `loc`, `msg` and `type` but drop `input` and `ctx`, so a rejected
  password, token or answer is not sent back.
  **Upgrade note:** self-hosters who used `/docs` on the internal APIs must set
  `API_DOCS_ENABLED=true`. The backend health check in `docker-compose.deployment.yml`
  now probes the public API document instead of `/api/v1/docs`; custom orchestration
  that probed `/docs` needs the same change.
- **Debug mode is off unless explicitly enabled.** `DEBUG` used to default to `true` in
  the backend, auth and Google integration services, and the deployment files did not set
  it, so a stack answered an unhandled server error with an HTML traceback (source, local
  paths). The code default is now `false`; the `.env.example` files set `DEBUG=true` for
  local development, and neither `.env.deployment` nor `docker-compose.deployment.yml` sets
  it (a pinned value would win over a change made in the portal).
  **Upgrade note:** self-hosters who relied on debug output must set `DEBUG=true`
  explicitly (for example in `.env.deployment`) and should turn it off again afterwards.
- **The client address can no longer be forged.** The backend used to believe
  `X-Forwarded-For` and `CF-Connecting-IP` from any private-network peer, so a request
  arriving through Swarm ingress or from another container could claim any address. It now
  trusts no proxy by default (the TCP peer is the client) and reads those headers only when
  the peer is inside `TRUSTED_PROXIES` (comma-separated IPs/CIDRs, IPv4 and IPv6;
  `API_TRUSTED_PROXIES` is accepted as an alias), walking `X-Forwarded-For` from the right
  and taking the first address that is not a trusted proxy. The backend warns once when a
  private peer sends forwarding headers while `TRUSTED_PROXIES` is empty.
  **Upgrade note:** self-hosters behind a reverse proxy or load balancer must set
  `TRUSTED_PROXIES` (in the root `.env`, passed through by
  `docker-compose.deployment.yml`) to the proxy's address(es), or all clients look like
  the proxy and share its rate limits. Hosted stacks that set `API_TRUSTED_PROXIES` keep
  working, but should list the private networks they previously relied on being trusted
  implicitly.
- **AI features are bounded.** Form generation's tool loop stops after
  `AI_MAX_TOOL_ITERATIONS` round trips (default 10) or `AI_MAX_TOOL_CALLS` tool calls (30)
  with a clear error; every call has an output token cap and timeouts (504 `ai_timeout`);
  model JSON is validated and retried once before a clean 502. The AI endpoints are rate
  limited per user (10/min) and per workspace (30/min) with a 429, and each workspace has a
  daily request and token counter with optional caps (`AI_DAILY_REQUEST_BUDGET`,
  `AI_DAILY_TOKEN_BUDGET`, off by default). Content people wrote is fenced as data in every
  prompt, and AI paths log error types and counts only. AI proposals apply only to the
  form version they were made from. See backend/AGENTS.md "AI limits".
- Smaller fixes: the response encryption helper always encrypts values that start with the
  ciphertext prefix; the Unsplash routes answer signed-in people only; an invitation can
  be deleted only within its own workspace; analytics events no longer carry the user's
  email; the document sandbox decodes and re-encodes logos and fetched pictures; a
  disabled billing owner keeps no break-glass access; the settings operations write only
  the caller's workspace.

## [3.4.0] - 2026-10-06

### Added

- **Several owners per workspace** with equal rights, managed on the Members page. A
  billing owner of a shared workspace cannot be deleted, and directory sync (SCIM)
  deactivates co-owners like any member.
- **Plain-language check in the builder**: rule-based tips under the question being
  edited.
- **Privacy panel on every respondent form** (English and Dutch), with honest defaults
  that are checked before a form is published, a "why we ask this" note per question
  (required of new forms only), and a retention period that is applied to every
  submission. Seeded contact questions say why they ask.
- Single sign-on tests explain what failed (new `sso_email_missing` code, claim names,
  Entra ID and Keycloak setup help).

### Fixed

- Polis listens on all of its networks; a deleted account's email is no longer sent to
  Brevo; the privacy panel states only what is true; publish checks see the builder's
  latest edits.

## [3.3.2] - 2026-10-06

### Fixed

- A custom domain that is being migrated can be removed and added again.
- Every webapp route is rendered per request, so runtime settings such as `SSO_ENABLED`
  take effect without a rebuild.

## [3.3.1] - 2026-10-06

### Added

- The single sign-on interface is switched on at runtime with `SSO_ENABLED`.

## [3.3.0] - 2026-10-06

### Added

- **Workspace roles**: Owner, Admin, Editor, Reviewer, Viewer and Privacy officer, with one
  authorization service behind forms, responses, members, settings, groups and imports.
  Members can be invited with a role and have their role changed; ownership can be
  transferred. Privacy officers complete deletion requests and never read answers. The
  webapp hides controls a member's role cannot use. The CSV download needs
  `response.export` on the server. See `docs/enterprise-access-model.md`.
- **Single sign-on** through Ory Polis, off by default (an overlay,
  `docker-compose.sso-deployment.yml`, runs it): "Sign in with SSO", a settings page for
  workspace owners, verified-domain and seat checks, SSO-required workspaces and Viewer as
  the default SSO role. See `docs/sso.md`.
- **Directory sync (SCIM)** on the single sign-on page: provisioning, group-to-role
  mapping, a resync with a safety stop, and seats that follow the directory.
- The hosted Custom Domain API is supported.

### Changed

- uv is pinned to 0.12.23 in the images and in CI, and the backend tests run on four
  parallel workers.

### Fixed

- Yes/no questions always offer Yes and No; rating stars register clicks and show the
  rating under the pointer; public forms get their own title and link preview; the
  responder header stays readable while scrolling and every answer field says Optional.

## [3.2.0] - 2026-10-04

### Added

- **Verified email domains**: a workspace proves it owns a domain with a DNS TXT record
  (Domains page). See `docs/verified-domains.md`.
- **Revocable sessions** with short-lived access tokens; the sessions are listed and can be
  ended in account settings.
- A permission catalogue and one authorization service (the first step of the roles in
  3.3.0).

### Security

- **The internal job API key must be configured.** The backend's internal job routes
  (called by the Temporal worker and the actions-executor with the `api-key` header)
  require a configured key: an unset, empty or `random_api_key` value is no longer
  accepted, the routes answer 503 until one is set, and the backend and both workers log an
  error at startup. The key is compared in constant time, and the settings no longer ship
  a default. **Upgrade:** `deploy.sh` generates `TEMPORAL_API_KEY` into the root `.env` and
  `docker-compose.deployment.yml` passes it to the backend and the worker; other
  deployments set the same value as `TEMPORAL_API_KEY` (backend) and `API_KEY` (worker,
  actions-executor).
- Only verified custom domains become allowed CORS origins.

### Fixed

- The owner of a disabled workspace keeps read and privacy access; workspace permissions
  are cached per user and dropped on sign-out; a failed domains fetch shows an error with a
  retry.

## [3.1.1] - 2026-10-04

### Security

- Workspace endpoints are scoped to members and their own data; provider sign-ins link to
  an account only by a verified email; only the backend may trigger notification mails and
  the auth service's internal API requires the internal key; the submitter's identity is
  taken only from the signed-in user; only admins switch responding to submissions.

### Fixed

- An account already deleted in auth counts as deleted.

### Added

- `docs/enterprise-access-model.md`: roles, permissions and form-level scope.

## [3.1.0] - 2026-10-03

### Added

- **Respond to submissions**: creators can add feedback to a response and the submitter is
  mailed a notice; enabling it is admin-only.
- A platform admin metrics page and `GET /admin/metrics` for platform admins;
  `PLATFORM_ADMIN_EMAILS` names them (removed again in 4.0.0, where the metrics live in
  the admin portal).

### Fixed

- The date picker's month arrows did nothing.

## [3.0.0] - 2026-10-03

### Added

- **PDF import**: upload a PDF and get a draft form, with progress and review screens.
  Pages are rendered and structured inside an isolated document sandbox container with a
  syscall filter; text is recovered (including legacy Devanagari fonts); filled-in answers
  are kept out of the questions; staff-only parts become internal fields and tables become
  repeating groups. A document is sent to an AI provider only with consent.
- **Repeating groups**: a group of questions respondents fill several times (one block per
  applicant, family member, employer, item) between a minimum and maximum, with "Add
  another <item>" / "Remove" controls and required questions per item. Answers are stored
  per item under the group (`{type: "group", items: [...]}`, additive: existing responses
  are unchanged) and limits are enforced on the server too. Inside an item, logic and pipes
  that refer to a sibling question use the same item; outside, logic works on the group as
  a whole and pipes offer the item count, a joined list and sum, average, minimum and
  maximum. The submission view shows one card per item. CSV and Google Sheets exports use
  columns per item for groups of up to 5 items and a separate table above that. The AI
  form-edit ops (chat, MCP) can create groups. Not yet: nested groups, hidden or calculated
  fields and file uploads inside groups, prefilling items.
- **Internal fields** that staff fill in after submission; they are never listed in
  on-submit action payloads.
- **AI consent**: workspaces opt in before any provider call, each form has its own consent
  for AI insights on responses, and respondents see an AI notice.
- A date picker label and date rules; headings in text blocks.
- **PostgreSQL support, opt-in**: a schema per service with Alembic, every repository
  behind a Mongo/Postgres routing seam, background jobs on Postgres (procrastinate), and a
  Mongo to Postgres migration CLI with a cutover runbook (`docs/postgres-cutover-runbook.md`).
  With every flag at its default the data stays in MongoDB.
- The custom-domain service is integrated through its SDK (`docs/custom-domain.md`).

### Changed

- Services refuse to start on a database schema older than the code. `deploy.sh` runs the
  migrations itself; a deployment that does not use it must run them before the release or
  set `DB_AUTO_MIGRATE=true` (see the cutover runbook). With every flag on Mongo nothing is
  checked.
- Response times are stamped on the server.

### Fixed

- Formula-like answers stay text in CSV and Google Sheets exports; file downloads are
  signed for the key the file is stored under; the responses table shows answers from every
  form version; form group visibility shows what was saved; a text answer is committed when
  the field loses focus; local variable values are never printed in tracebacks.

## [2.3.4] - 2026-09-06

### Fixed

- Form all-submissions requires workspace membership.

## [2.3.3] - 2026-09-02

### Added

- A legacy invitation page and better invitation handling.

### Changed

- The deployment workflow is simplified and deploys through Docker Manager (see
  `README.md`, "CI deployments").

## [2.3.2] - 2026-08-24

### Added

- AI response summaries and insights (opt-in), AI edits of form settings (purpose,
  retention and trust metadata), and conditional-logic operations plus a blank `create_form`
  MCP tool.
- PKCE for the Google OAuth sign-in.
- S3-compatible storage configuration, with RustFS for local development.

### Changed

- One `react-i18next` instance across the webapp (translations had broken); dependency
  majors migrated and unused dependencies removed.

### Fixed

- The post-submit crash on forms without a thank-you page; the builder and form cards show
  the workspace identity instead of the product logo; PRO activation errors are surfaced; the
  access token is re-minted when the plan changes out of band.

## [2.3.1] - 2026-07-13

### Fixed

- Analytics parameter names for Umami 3.x.

## [2.3.0] - 2026-07-13

A trust-first redesign of the responder form, the builder and the dashboard, AI-assisted
form building, form theming, and self-hosted analytics.

### Added

- **AI-assisted form building**: a form-editing engine, an AI profile of your organisation
  that grounds generation, a chat panel in the builder, a compliance review with per-finding
  fixes, a living preference memory, and workspace API keys with an MCP server.
- **Answer piping / recall**: question titles can reference earlier answers or hidden fields
  ("Thanks, @name!") via an "@ Answer" menu in the builder's title toolbar, resolved live for
  responders. Plain-text surfaces support `{{field:<id>}}` / `{{hidden:<name>|fallback}}`
  tokens. Pipes referencing deleted fields are pruned automatically.
- **Hidden fields (URL parameters)**: creators declare parameter names (for example
  `utm_source`) form-wide; values are captured from the share link (declared names only),
  submitted with the response, encrypted at rest like answers, and shown in the response
  detail view. `?field_<id>=value` parameters prefill text-like input fields.
- **Theming**: custom theme colours, saved workspace themes (Themes page), theme dropdown,
  backgrounds (colour, gradient, pattern or image), form styles (classic, sheet, studio), a
  12-column grid for field widths, and contrast-verified presets (WCAG 2.1).
- **Conditional logic** with a flow (graph) view of jumps, drop-off analytics, and a tabular
  input field.
- Branded 404 and 500 pages, human-friendly default form slugs, richer form-list cards.
- Self-hosted product analytics: Umami ships as a Docker Compose service (its own Postgres)
  and the backend finds or creates its Umami website on startup, so no self-hosted
  deployment phones home. Form views are attributed to a canonical
  `/{workspace_name}/forms/{slug}` path. A flow-native template gallery is seeded on startup.
- `docker-compose.deployment.yml` health checks with `depends_on: condition: service_healthy`
  gating; `deploy.sh` starts Umami and generates `UMAMI_APP_SECRET` on first run.
- Open-source community files (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  issue and PR templates, `SUPPORT.md`, `GOVERNANCE.md`, `ROADMAP.md`, `CODEOWNERS`, this
  changelog), `AGENTS.md` guidance files, `docs/ARCHITECTURE.md`, continuous integration
  (`ci.yml`), Dependabot configuration, a frontend test suite (Vitest + Testing Library)
  and Mailpit for local email.

### Changed

- **Responder form and portal redesigned for trust.** Questions render at 24px/600 ink with
  one bordered input per field type and a visible themed focus ring; buttons say what
  happens; a trust strip links "How your data is used" and "View or delete your response",
  and is visible while building. The responder portal (where "view or delete your response"
  lands) shows the form's purpose, identifiable receipts and the right to delete, and
  submission details wear the workspace's brand, not the platform's.
- **Builder.** Insert, Text block and Logic are always visible; a Saving / Saved indicator
  reports autosave; page duplicate remaps internal references; a Fit / 100% zoom; the
  drawer is split into Page, Form and Design tabs; trust and privacy are authored in the
  Form tab; the builder loads the draft it edits.
- **Form details page** has five always-visible tabs (Preview, Responses, Analytics, Share,
  Settings); the sidebar is grouped into Collection, Your site and Workspace; one vocabulary
  (workspace and site); workspace settings open inside the site frame.
- **Forms and responses are unlimited on every plan**, and the dashboard chrome is
  de-branded (a quiet "Powered by bettercollected" caption).
- **Anonymity now holds at the account level**: verifying your email no longer links
  anonymous submissions to your account, and an anonymous response is reachable only
  through its submission number.
- Corrected `docs/DEVELOPERS_GUIDE.md` to the uv + yarn workflow, rewrote `README.md`, sped
  up the backend test suite (about 137s to 5s), aligned toolchain versions, and batched
  routine dependency updates.

### Fixed

- **Anonymity is enforced.** The backend accepted the `anonymize` flag but stored the
  signed-in email as `dataOwnerIdentifier` anyway. Anonymous responses now store no owner
  identifier and no email, only a one-way hash so the responder can still find and delete
  their own submission, and anonymous responders can request deletion. Sharing your identity
  is opt-in (the checkbox starts unchecked).
- Deletion requests can be fulfilled from the dashboard, with a confirmation, and the
  table and counters refresh.
- Umami pageview double-counting (automatic tracking off, one canonical event per form
  view) and the `/stats` endpoint against current self-hosted Umami.
- `docker-compose.deployment.yml`: Temporal's `DB=postgresql` was never a valid driver name
  (Temporal had likely never started successfully through this file), and Temporal's
  Postgres is pinned to `postgres:15-alpine` on a named volume. `install.sh` referenced
  Poetry and a per-service `Makefile` that no longer exist and is rewritten to `uv sync`.
- Google login (canonical OAuth scopes), the Temporal client and the OTP mail on the main
  event loop, startup crashes with pydantic v2 and beanie 2.x, forms listing pagination,
  React 19 form-rendering crashes, the editor auto-saving on load, and numerous Dependabot
  security advisories.

### Security

- Removed committed Stripe/Sentry secrets from `auth/.env.example` (placeholders now).
  **Note:** these values still exist in git history and should be rotated and scrubbed
  before/at public release; see `SECURITY.md`.

## [2.2.0] - 2026-02-27

- Baseline for this changelog. See the
  [v2.2.0 release](https://github.com/bettercollected/bettercollected/releases/tag/v2.2.0)
  and earlier tags for prior history.

[Unreleased]: https://github.com/bettercollected/bettercollected/compare/v4.0.0...HEAD
[4.0.0]: https://github.com/bettercollected/bettercollected/compare/v3.4.0...v4.0.0
[3.4.0]: https://github.com/bettercollected/bettercollected/compare/v3.3.2...v3.4.0
[3.3.2]: https://github.com/bettercollected/bettercollected/compare/v3.3.1...v3.3.2
[3.3.1]: https://github.com/bettercollected/bettercollected/compare/v3.3.0...v3.3.1
[3.3.0]: https://github.com/bettercollected/bettercollected/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/bettercollected/bettercollected/compare/v3.1.1...v3.2.0
[3.1.1]: https://github.com/bettercollected/bettercollected/compare/v3.1.0...v3.1.1
[3.1.0]: https://github.com/bettercollected/bettercollected/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/bettercollected/bettercollected/compare/v2.3.4...v3.0.0
[2.3.4]: https://github.com/bettercollected/bettercollected/compare/v2.3.3...v2.3.4
[2.3.3]: https://github.com/bettercollected/bettercollected/compare/v2.3.2...v2.3.3
[2.3.2]: https://github.com/bettercollected/bettercollected/compare/v2.3.1...v2.3.2
[2.3.1]: https://github.com/bettercollected/bettercollected/compare/v2.3.0...v2.3.1
[2.3.0]: https://github.com/bettercollected/bettercollected/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/bettercollected/bettercollected/releases/tag/v2.2.0
