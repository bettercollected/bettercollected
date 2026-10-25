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

- Single sign-on: a deleted workspace's connections that the identity bridge (Polis) could not delete
  are no longer dropped silently. They are kept as `release_pending`, never sign anyone in, and a daily
  job (`sso_release_retry`) deletes them in Polis, so they stop holding the identity provider's entity
  ID. A support command, `python -m backend.sso entity-id <entity id>`, shows which connections hold an
  entity ID and, with `--apply`, releases orphaned ones (a named workspace's only on request). The SSO
  docs now say that a workspace's identity provider controls the whole account of users on its
  verified domains, their other workspaces included.
- The sign-in code, invitation and submission-update mails are available in Dutch. The backend endpoints
  that send them take an optional `locale` (`nl`, or a tag such as `nl-NL`; anything else gets
  English), and the submission-update notice follows the form's language. The invitation now names the
  workspace as "<workspace> via <instance name>". It names the inviter with the role they offer and
  says that the name is the one the inviter chose.
- Two SQL scripts for the Umami database, `scripts/umami/email-data-count.sql` (read-only) and
  `scripts/umami/email-data-purge.sql` (a dry run unless `-v apply=1`), count and delete the `email`
  event-data property that the web app sent before it stopped sending the signed-in user's email to
  analytics. They print counts only.
- Deleting an account now also erases its Brevo marketing contact (`DELETE /v3/contacts/{email}`), with
  a separate Brevo API key, `BREVO_CONTACTS_API_KEY` (never the tracker key). Without the key the
  erasure is skipped. Rate limits and server errors are retried a few times with backoff. It never holds
  up the deletion, and the log names only the user id.
- For accounts deleted earlier, `python -m auth.brevo_contacts` (auth container; the key comes from the
  container's environment or a hidden prompt, never the command line) counts the Brevo contacts that have
  no account, broken down by a marker attribute and by Brevo list membership, and lists the attribute
  names they carry. It prints counts and attribute names only. `--apply` needs `--marker ATTRIBUTE[=VALUE]`.
  It deletes only contacts that have no account, carry the marker and are on no Brevo list.
- `GOOGLE_FORMS_IMPORT=on|readonly|off` (backend and Google Forms service; default `on`). `readonly` keeps
  imported forms and responses readable but refuses new imports, re-syncs, account connections and every
  other call to Google with a Google Forms credential (403 `google_forms_readonly`); `off` answers 410
  `google_forms_off` and never calls the Google Forms service. `GET /providers` reports the mode
  (`importMode`). See `docs/RUNNING_INTEGRATIONS.md`.

### Removed

- **Typeform** (services): the Typeform sign-in (always refused, since its email is not verified) and its
  settings are gone. `/auth/{provider}/basic` takes Google only, and the import and proxy routes no longer
  accept `typeform`. Forms and responses imported from Typeform stay readable as ordinary forms. The
  `TYPEFORM_*` settings are retired: values left in an env file or the settings store are ignored and no
  longer reported. A stored `typeform` provider row is no longer offered, read or called (the OAuth
  callback and every provider lookup refuse it), so account deletion no longer depends on the Typeform
  service. The row itself stays in `forms_plugin_configs` and is pruned with the other Typeform data later. The keyset tasks accept and ignore `typeform_acknowledged`
  and no longer wait for a Typeform heartbeat.
- **Typeform** (deployment): the `integrations-typeform` compose service, `.env.typeform`, the
  `TYPEFORM_*` lines of `.env.deployment.example` and the Typeform seed row are gone.
  `./deploy.sh typeform` and `./deploy.sh both` still work, with a warning, and start the stack
  without Typeform (with Google Forms for `both`); `settings-prune` ignores `--typeform` and
  `--no-typeform`. `deploy.sh` warns when an `integrations-typeform` container from an earlier
  release still exists and never removes it; existing `.env.typeform` files are left alone.

## [4.0.13] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations, roles, SQL or new settings,** and no compose change.
- **Cutover operators (Stage 0):** on 4.0.12 a clean full `verify` could not write the `backend`
  marker, because the groups holding TTL collections (`identity`, `analytics`) were never
  recorded. After this deploy, run a full `verify` in the `backend` container
  (`python -m backend.migrate verify`), then `python -m backend.migrate status`: it should show
  `marker: verified`. `auth` and `google` need nothing new.
- **Forms groups on Postgres:** this release is required before the forms group moves to
  `postgres_primary_dual`. Under `dual` nothing changes.
- **Responder groups:** links to another workspace's group made before this release stay listed
  on the form until its groups are saved again or the link is removed; any save drops them. To see
  whether any exist, run this read-only, counts-only query on the app database (the Postgres
  mirror, which a clean `verify` of the `forms` and `responses` groups shows matches Mongo):

  ```sql
  SELECT
    count(*) AS links_total,
    count(*) FILTER (WHERE g.id IS NULL) AS links_to_missing_group,
    count(*) FILTER (WHERE g.id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM app.workspace_forms wf
        WHERE wf.form_id = l.form_id AND wf.workspace_id = g.workspace_id))
      AS links_to_foreign_group,
    count(DISTINCT l.form_id) FILTER (WHERE g.id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM app.workspace_forms wf
        WHERE wf.form_id = l.form_id AND wf.workspace_id = g.workspace_id))
      AS forms_with_foreign_group
  FROM app.responder_group_form l
  LEFT JOIN app.responder_group g ON g.id = l.group_id;
  ```

  `links_to_foreign_group` counts links whose group belongs to none of the form's workspaces;
  `links_to_missing_group` counts links to a deleted group, which are not listed. If either is
  above 0, a removal step follows in a later release.
- **Rollback:** 4.0.12 can run against a 4.0.13 database. Marker rows written by 4.0.13 carry two
  more count keys, which 4.0.12 ignores.

### Fixed

- **Migration `verify` records groups that hold expired TTL copies.** A clean `verify` refused to
  record a group (and so the service marker) when a collection Mongo expires by a TTL index held
  expired copies in only one store, because it still compared the raw counts. It now compares the
  live counts, without the expired copies, and the report counts those per store
  (`expired_mongo`, `expired_postgres`; `expired` stays the total). The recorded counts are the
  live ones, with the expired copies beside them. `verify` still deletes nothing.

### Security

- Forms served from Postgres (`DB_WRITE_MODE__forms=postgres_primary_dual` and beyond) no longer
  undo a change made at the same time: setting or removing a form's logo changes only the logo
  (as MongoDB's update of the logo alone does), and the builder's save, an action's secret, a
  form's workspace settings and a template's content are applied to the stored copy under its
  row lock, instead of saving a copy read before. Such a write no longer brings back a removed
  action's encrypted credentials, undoes an autosave, or stores a deleted form, form link or
  template again.
- Responder groups: a form's responder groups can only be set to groups of the form's workspace.
  Linking another workspace's group to a form, which then listed that group's name and email
  pattern with the form, is refused (404, as for an unknown group) and links nothing, even when
  the other ids in the request are the workspace's own. Groups already linked to the form may be
  sent again: on a form held by several workspaces, each sets and removes only its own groups and
  the others' stay linked, and a link to another workspace's group made before this check is
  dropped when the form's groups are saved (or can be removed on its own). A workspace's group
  listing skips a link to another workspace's form instead of failing.

## [4.0.12] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations, roles, SQL or new settings,** and no compose change.
- **Case-duplicate accounts:** 4.0.11's `auth.resolve_case_duplicate_accounts` could not reach the
  API and refused every run with `backend_unreachable`. After this deploy, run it as the 4.0.11
  notes describe:
  1. Set one fresh `ADMIN_TASKS_API_KEY` on `backend` and `task-runner`, only for the run.
  2. Check that none of the listed accounts has its own deletion pending.
  3. Run the dry run and review it, then apply.
  4. Handle the `manual` groups and any `refused` drops with the people concerned.
  5. Unset the key on both services.

  A refused run now names its cause; `docs/admin-service.md` has a troubleshooting table.
- **Cutover operators:** `resolve-outbox` is new. It is only needed after a group is rolled back
  from `postgres_primary_dual` to `dual` (Phase 2); see the runbook's "Stuck case". Stage 0 does
  not need it.
- **Rollback:** 4.0.11 can run against a 4.0.12 database; nothing is stored differently.

### Added

- `python -m <service>.migrate [--group g] resolve-outbox [--apply]`: after a group rolls back
  from `postgres_primary_dual` to `dual`, it resolves the Postgres-side outbox entries whose
  write Mongo provably holds (the same checksum for every row the entry names and every row of
  the group, in both stores), so `reconcile` and `verify` can get clean again. Rows where Mongo
  only has a later-stamped, different version (`superseded`) are kept unless the operator adds
  `--accept-superseded` after confirming Mongo's version should win. A dry run by default, it
  prints counts only; `--ids-file` writes ids to a new local file. The runbook's "stuck case"
  uses it instead of manual SQL.

### Fixed

- Admin task `auth.resolve_case_duplicate_accounts`: a refused run now says why. The runner
  refuses with `backend_unreachable` (connection or timeout only), `backend_route_missing`
  (404), `backend_redirect` (3xx, never followed), `backend_error` (5xx or another status) or
  `backend_bad_reply` (not the expected JSON), and logs the HTTP status. When the API's call to
  the auth service fails, the internal admin-task routes answer 502 with a stable code instead
  of passing auth's status through, and the run refuses with `auth_unreachable`,
  `auth_key_refused` (the backend's `AUTH_INTERNAL_NOTIFY_KEY` does not match auth's),
  `auth_misconfigured` or `auth_error`; an account deletion that cannot be started (Temporal or
  the jobs worker down) refuses with `deletion_unavailable` instead of `backend_key_missing`.
  The admin service guide has a troubleshooting table for these codes.
- Admin task `auth.resolve_case_duplicate_accounts` no longer refuses every run with
  `backend_unreachable`: the runner requested the API's routes with a trailing slash, which the
  API answers with a redirect the runner does not follow. It now requests their exact paths.

## [4.0.11] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations and no new roles or SQL.** Two new settings, both environment only, for the
  case-duplicates task:
  - `ADMIN_TASKS_API_KEY` on `backend` **and** `task-runner` (the same value);
  - `ADMIN_TASKS_BACKEND_URL` on `task-runner`. The default is `http://backend:8000/api/v1`, which
    works when `task-runner` shares a network with `backend`.

  Without the key, the internal admin-task routes answer 503 and the task refuses; nothing else
  changes.
- **Hosted deploys:** `deploy.yml` now always updates `admin`, `document-sandbox`, `jobs-worker` and
  `task-runner` with the backend image. Every stack the workflow deploys must run these four, or
  Docker Manager rejects the deploy. Delete the repository variables
  `DEVELOP_BACKEND_IMAGE_SERVICES`, `STAGING_BACKEND_IMAGE_SERVICES` and
  `PROD_BACKEND_IMAGE_SERVICES`; they are no longer read.
- **Accounts whose emails differ only in case** (they must be resolved before 4.1):
  1. Set one fresh random value (`openssl rand -hex 32`) as `ADMIN_TASKS_API_KEY` on `backend` and
     `task-runner` and redeploy those two, **only for the run**.
  2. Check that none of the listed accounts has its own deletion already pending.
  3. Run `auth.resolve_case_duplicate_accounts` as a dry run and review the decision per group:
     keep, drop or manual. Then apply.
  4. Handle the `manual` groups (two or more accounts with forms) and any `refused` drops with the
     people concerned.
  5. **Unset `ADMIN_TASKS_API_KEY` on both services** right after.

  `auth.migrate preflight` now prints `case_variant_keys` and `case_variant_documents` (a warning on
  4.0), so the count is visible at any time.
- **Account deletion and Google Forms:** deleting an account now removes only its own Google
  credentials, by user id, plus the legacy ones without a user id that carry its email. Another
  account connected to the same Google account keeps its connection.
- **Migration (cutover operators):**
  - `verify` ignores copies that Mongo's TTL index has expired, and reports them under `expired`.
  - `reconcile` (Mongo → Postgres) keeps a newer application-written Postgres row and reports it
    as `newer_in_postgres`, instead of skipping it silently. To copy Mongo's version over such rows
    while Mongo is the primary, run `reconcile --direction mongo->postgres --mongo-wins` with the
    services' `DB_WRITE_MODE` (or `DB_WRITE_MODE__<group>`) **set explicitly** in the runner's
    environment. Groups without an explicit `mongo` or `dual` are never overwritten, and nothing
    the application wrote is overwritten while the Postgres-side outbox has unresolved entries.
  - A `mongo->postgres` run no longer resolves Postgres-side outbox entries; `postgres->mongo` or a
    clean full `verify` does.
  - See `docs/postgres-cutover-runbook.md` (Phase 1 step 5, and the Phase 2 rollback step).
- **Rollback:** 4.0.10 can run against a 4.0.11 database. The new settings go unused, and the
  migration tools behave as in 4.0.10.

### Added

- **Admin task `auth.resolve_case_duplicate_accounts`** resolves accounts whose emails differ only
  in case, which 4.1 refuses to start with. Per group: accounts without forms are dropped; if one
  account has forms it stays; if none has, the one created last stays; if two or more have forms,
  those are listed for manual handling. The dry run lists every group (account ids, created time,
  forms count, decision; never an email); the apply deletes each dropped account through the
  product's own account deletion and reports the groups that remain. It needs the same new
  `ADMIN_TASKS_API_KEY` on the `backend` and `task-runner` services (docs/admin-service.md).
- **`auth.migrate preflight` counts accounts whose emails differ only in letter case**
  (`case_variant_keys`: distinct emails held by more than one account; `case_variant_documents`:
  the accounts involved), as a warning with counts only. A later release makes an email unique
  ignoring case, so these accounts have to be merged before upgrading; on 4.0 they keep working
  and preflight still passes.

### Changed

- Deploys through `.github/workflows/deploy.yml` update the services that run the backend image under
  their own stack service name (`admin`, `document-sandbox`, `jobs-worker`, `task-runner`) every time;
  the `DEVELOP_`/`STAGING_`/`PROD_BACKEND_IMAGE_SERVICES` repository variables are gone. Every stack the
  workflow deploys must run these four services. Operators: delete those repository variables after
  upgrading; they are no longer read.

### Fixed

- **Deleting an account no longer deletes another account's Google Forms connection.** The Google
  Forms integration removed every stored credential with the deleted account's email address, so
  a second account connected to the same Google account lost its connection too. It now removes
  the account's own credentials by user id, and by email only the legacy ones that have no user id.
- **Migration `verify` agrees with `reconcile`.** In collections Mongo expires by a TTL index
  (sessions, rate-limit counters, SSO states, …), `verify` now treats an expired copy in either
  store as absent, as `reconcile` already did, so copies Mongo's TTL monitor dropped are no longer
  reported as `missing_in_mongo` on every run; the report counts them under `expired`. Only a date
  expires, as in Mongo: an ISO-string expiry is a live copy. And `reconcile` (Mongo → Postgres) no
  longer skips a Postgres row the application wrote after Mongo's copy without a trace: it keeps
  it and counts it as `newer_in_postgres`. The new `reconcile --mongo-wins` copies Mongo's version
  over such rows instead, only in the groups whose `DB_WRITE_MODE`/`DB_WRITE_MODE__<group>` is
  explicitly `mongo` or `dual`. While the Postgres-side outbox has unresolved entries (writes from
  a time Postgres was primary), no row the application wrote is replaced at all; a `mongo->postgres`
  run no longer resolves those entries (`postgres->mongo` or a clean full `verify` does).

## [4.0.10] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations.** No service schema changes, no new service settings and no compose change.
- **Once, after the deploy: create the purge task's role and function.** `deploy.sh` does this
  (it runs `postgres/ensure-admin-roles.sh`). Without `deploy.sh` (a Swarm stack, say), run the
  statement below once **as the database superuser, connected to the application database**. It is
  self-contained: no psql variables and no passwords, because it only creates the login-less role
  `bc_tasks_purge_google` and the function `google.purge_unencrypted_credentials`, and grants
  EXECUTE to `bc_tasks_data_google` (created for 4.0.8). It is safe to run again. Running the whole
  `ensure-admin-roles.sh` as described for 4.0.8 does the same. Until it has run, the task refuses
  with `purge_function_missing`; nothing else depends on it.

  ```sql
  DO $gpurge$
  DECLARE
      s text;
  BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_tasks_purge_google') THEN
          CREATE ROLE bc_tasks_purge_google NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE;
      END IF;
      ALTER ROLE bc_tasks_purge_google NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ALTER ROLE bc_tasks_purge_google SET search_path = pg_catalog;
      EXECUTE format('REVOKE ALL ON DATABASE %I FROM bc_tasks_purge_google', current_database());
      FOREACH s IN ARRAY ARRAY['app', 'auth', 'google', 'jobs', 'admin', 'tasks', 'settings'] LOOP
          IF to_regnamespace(s) IS NOT NULL THEN
              EXECUTE format('REVOKE ALL ON SCHEMA %I FROM bc_tasks_purge_google', s);
              EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM bc_tasks_purge_google', s);
              EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM bc_tasks_purge_google', s);
          END IF;
      END LOOP;
      IF to_regnamespace('google') IS NULL THEN
          RETURN;
      END IF;
      GRANT USAGE ON SCHEMA google TO bc_tasks_purge_google;
      IF to_regclass('google.oauth_credentials') IS NOT NULL THEN
          GRANT SELECT (user_id, doc), DELETE ON google.oauth_credentials TO bc_tasks_purge_google;
      END IF;
      EXECUTE $create$
  CREATE OR REPLACE FUNCTION google.purge_unencrypted_credentials(p_apply boolean) RETURNS bigint
  LANGUAGE plpgsql SECURITY DEFINER VOLATILE
  SET search_path = pg_catalog, pg_temp AS $fn$
  DECLARE
      n bigint;
  BEGIN
      IF p_apply IS NULL THEN
          RAISE EXCEPTION 'google.purge_unencrypted_credentials: apply must be true or false'
              USING ERRCODE = 'invalid_parameter_value';
      END IF;
      IF p_apply THEN
          WITH gone AS (
              DELETE FROM google.oauth_credentials c
               WHERE coalesce(c.user_id, '') = ''
                  OR (jsonb_typeof(c.doc -> 'credentials') = 'object'
                      AND NOT (c.doc -> 'credentials') ? '$binary')
              RETURNING 1
          )
          SELECT count(*) INTO n FROM gone;
      ELSE
          SELECT count(*) INTO n FROM google.oauth_credentials c
           WHERE coalesce(c.user_id, '') = ''
              OR (jsonb_typeof(c.doc -> 'credentials') = 'object'
                  AND NOT (c.doc -> 'credentials') ? '$binary');
      END IF;
      RETURN n;
  END
  $fn$
  $create$;
      ALTER FUNCTION google.purge_unencrypted_credentials(boolean) OWNER TO bc_tasks_purge_google;
      REVOKE ALL ON FUNCTION google.purge_unencrypted_credentials(boolean) FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION google.purge_unencrypted_credentials(boolean) TO bc_tasks_data_google;
  END
  $gpurge$;
  ```
- **Mongo:** the task runner's Mongo user (`TASK_RUNNER_MONGO_URI`) needs `readWrite` on
  `Oauth2CredentialDocument` in the Google integration's database. It already has that if it has run
  `keyset.reencrypt`.
- **Then run the purge task** in the admin portal: `google.purge_unencrypted_credentials` with
  `stores: auto`, a dry run first (counts per store), then the apply. It replaces the manual runbook
  step "Google credentials without a user id"; don't run both.
- **Hosted deploys:** set the repository variable `PROD_BACKEND_IMAGE_SERVICES` to the services of the
  production stack that run the backend image (`docker service ls`), so the next tag also updates
  them. Empty, deploys behave as before.
- **API keys:** a request whose key is revoked while it is in flight is now refused (401) instead of
  bringing the key back.
- **Before moving the identity group to `postgres_primary_dual`:** this release must be deployed
  (workspace settings written atomically in Postgres).
- **Rollback:** 4.0.9 can run against a 4.0.10 database. The role and function stay unused.

### Added

- Admin portal: a task, `google.purge_unencrypted_credentials`, replaces the manual runbook step
  "Google credentials without a user id". It deletes the stored Google credentials that have no user
  id or hold readable tokens, with exactly the runbook's filters: a dry run first (counts per store),
  then the apply with the usual confirmation code, Mongo first and then Postgres, with the counts in
  the audit log. Counts only, never ids, emails or tokens; a second run deletes nothing. An apply
  must cover every store the services still write (`stores_incomplete` otherwise). The task
  runner's Google data role still has no DELETE: it calls a narrow definer function,
  `google.purge_unencrypted_credentials`, owned by a new login-less role `bc_tasks_purge_google`.
  Both are created by `postgres/ensure-admin-roles.sh`: run it once after upgrading (`deploy.sh`
  does; without `deploy.sh`, as described for 4.0.8). Until then the task refuses with
  `purge_function_missing`. Mongo: the runner's Mongo user needs `readWrite` on
  `Oauth2CredentialDocument`.

### Fixed

- Deploys through `.github/workflows/deploy.yml` can now also update the stack services that run the
  backend image under their own name (`admin`, `document-sandbox`, `jobs-worker`, `task-runner`). They were
  always left on their old image tag. Each environment lists the ones its stack runs in a new repository
  variable (`DEVELOP_BACKEND_IMAGE_SERVICES`, `STAGING_BACKEND_IMAGE_SERVICES`, `PROD_BACKEND_IMAGE_SERVICES`;
  empty by default, so nothing changes until it is set). See "CI deployments" in the README.

### Security

- A workspace API key revoked while a request using it was in flight stays revoked: recording the
  key's last use now changes only that field, and only while the key is not revoked (a conditional
  update in MongoDB and Postgres), instead of saving the request's copy of the whole key, which
  could set it back to not revoked. Such a request is refused.
- Workspace settings changed field by field (AI consent, single sign-on enforcement and default role,
  custom-domain status) are written atomically when the workspaces are served from Postgres
  (`DB_WRITE_MODE__identity=postgres_primary_dual` and beyond): two changes made at the same time
  both stay, so a concurrent save can no longer switch AI back on without consent or turn off
  required single sign-on. Upgrade before moving the identity group to Postgres.

## [4.0.9] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations.** No service schema changes, no new settings and no compose change.
- **Deploy the backend and the Google Forms service together.** The Google Sheets credential now
  travels in the request body, so both must run 4.0.9.
- **Once, after the deploy: remove Google credentials without a user id.** Run the Mongo step
  first, then the Postgres step, as described in `docs/postgres-cutover-runbook.md` ("Google
  credentials without a user id"). Both print counts only and are safe to run again. The owners of
  the deleted rows connect Google Forms again on their next import; imported forms and responses
  are kept.
- **Seeded templates move to Leaflet on the first start.** The backend updates the predefined flow
  templates once. A theme or section title changed by hand is kept, and forms already made from a
  template keep their own theme.
- **Adding a Google Sheets action with caller-supplied secrets is now refused** (422
  `action_secrets_not_allowed`). The Google Sheets connection flow is unaffected.
- **Single sign-on:** an instance with `SSO_ENABLED=true` that lacks some SSO settings now says so.
  The workspace SSO page shows "switched on but not fully set up", and the Health page lists the
  missing settings by name.
- **Rollback:** 4.0.8 can run against a 4.0.9 database. Roll back the backend and the Google Forms
  service together. Deleted credentials stay deleted, and their owners reconnect.

### Changed

- The predefined flow templates (Support triage, Lead qualification, Job application with screening) use the
  Leaflet design that new forms start with, each welcome page says in one line what the form is for, and each
  page has a short section title, so Leaflet's section bar no longer repeats the page's first question.
  Templates seeded by an earlier version get these on the next backend start, once; a theme or section title
  changed by hand is kept, and forms already made from a template keep their own theme.

### Fixed

- Google Forms: the import routes now look up the signed-in user's Google credential
  through the routed credential repository, so they follow `DB_READ_SOURCE` /
  `DB_WRITE_MODE` (and their `__google` overrides) like the rest of the service. They
  always read MongoDB before, which would have missed credentials once the google group
  reads from Postgres.
- Single sign-on switched on (`SSO_ENABLED=true`) but not fully set up no longer claims to be off: the workspace
  SSO page now says it is switched on but not fully set up yet (English and Dutch; the overview API answers
  `reason: "not_configured"`, and `reason: "disabled"` when it is off), the backend and auth log the missing
  settings by name at startup, and the admin portal's Health page lists them per service. Names only, never values.
- Forms made from the predefined flow templates no longer start with field borders too faint to see
  (1.6:1 against the page); the templates' old theme is replaced by Leaflet, which meets WCAG 2.2 AA.
- Templates page: the Default section no longer cuts off its second row of templates; the cards wrap in a
  grid that fits the screen, titles use the full card width, the section looks the same in every language,
  and each preview shows the template's own title instead of an empty page with only a Start button.

### Security

- Google Forms: a stored Google credential is never written unencrypted. Legacy rows
  connected by older versions have no user id to derive the encryption key from, and every
  token refresh stored their access and refresh tokens in plain text; such an update now
  writes nothing, and reconnecting gives the row the signed-in user's id. An update without
  a stored credential no longer fails. Operators: delete the remaining legacy rows once, as
  described in `docs/postgres-cutover-runbook.md` ("Google credentials without a user id").
- Google Sheets action: adding the action with caller-supplied secrets is refused (422
  `action_secrets_not_allowed`, nothing is written); only the Google Sheets connection flow
  stores its credential. Other actions still take secrets.
- Google Forms service and actions executor: Google access tokens are refreshed only at Google's
  token endpoint (the configured `GOOGLE_TOKEN_URI` in the Google Forms service, including
  google-auth's own refresh; in the actions executor, Google's documented endpoints). The token
  address stored inside a credential is no longer trusted, so a forged credential cannot make
  either service send a client secret and refresh token to another host.
- The Google Sheets credential now travels from the backend to the Google Forms service in the
  request body instead of the query string, so it no longer reaches access logs. Backend and
  Google Forms service must run the same release.

## [4.0.8] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations.** No service schema changes, no new settings and no compose change.
- **Run `postgres/ensure-admin-roles.sh` once after the deploy.** It creates the definer functions
  behind the Health page's migration heads and mirror outbox. It is idempotent. `deploy.sh` runs it
  on every deploy.
  - **Without `deploy.sh` (a Swarm stack, say):** run it once as the database superuser, from a
    one-off container with `psql` 15 or newer (the `postgres:16` image) that can reach the database.
    Give it `PGHOST`, `PGPASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` and the five `BC_*_PASSWORD`
    values (`BC_ADMIN_PASSWORD`, `BC_ADMIN_MIG_PASSWORD`, `BC_TASKS_PASSWORD`,
    `BC_TASKS_DATA_APP_PASSWORD` and `BC_TASKS_DATA_GOOGLE_PASSWORD`).
  - **Use the values the stack already uses:** the script sets these roles' passwords, so a
    different value locks the admin portal and the task runner out.
  - **Until it runs,** the Health page shows those three schemas as "not available" and names the
    script. Nothing else depends on it.
- **Forms with logic on choice questions change behaviour.** On multiple choice and dropdown
  questions, visibility rules and page jumps now work as they were designed: questions show and
  hide, jumps fire and endings are chosen. Before, these conditions never matched. Forms that relied
  on that (a question that "never showed") will now follow their rules, so review forms whose logic
  tests a chosen option. Piped choice answers now show the option's text instead of its internal id.
- **Operators: `reconcile --direction postgres->mongo` now needs `postgres_primary_dual`.** It exits
  with code 2, naming each group and its mode, unless every group it covers is on that write mode.
  Run it with the services' flags. `--dry-run` and mongo->postgres are unchanged.
- **Rollback:** 4.0.7 can run against a 4.0.8 database. The new functions stay unused, and 4.0.7
  treats a `CopyUnverified` outbox entry as an ordinary entry that `reconcile` resolves.

### Added

- The admin portal's Health page now shows the `app`, `auth` and `google` schemas'
  migration state against the head the deployed code expects, next to `admin`, and a
  "Mirror outbox" table with the unresolved and total mirror-write failures of each
  service in PostgreSQL (red while any is unresolved). Both are read through narrow
  definer functions created by `postgres/ensure-admin-roles.sh`; run it once after
  upgrading (`deploy.sh` does). MongoDB outboxes are not shown.

### Fixed

- Logic on multiple choice and dropdown questions works. Visibility rules and page jumps that test
  which option a respondent chose never matched: answers hold the chosen option's id, while the
  logic editor, the AI assistant and the seeded "Support triage" template name the option by its
  text. So such questions stayed hidden (or shown), jumps never fired, a jump never chose its
  ending, and the flow view counted every response on the linear path. Conditions now match the
  chosen option by its text or its id (exactly, as before), in the respondent's browser and in the
  server's checks alike; several answers are tested for membership the same way, and text typed as
  "Other" is compared as it is (an "Other" answer is no longer empty). Existing rules work without
  changes. Affected every release since conditional logic shipped in 2.3.0.
- Mirror convergence is capped as a whole, at twice the mirror timeout and including its writes, so a
  hung store can no longer hold a request longer; a copy cut off by the cap is still re-checked. A copy
  whose re-check failed is recorded in the outbox as `CopyUnverified`, and only a clean full `verify`,
  not `reconcile`, resolves it.
- Answer piping shows a choice answer as the option's text. A multiple choice or dropdown answer
  recalled in a later question, description, ending or repeating-group item title (or listed across
  a group's items) showed the chosen option's internal id instead of the words the respondent picked,
  and text typed as "Other" was left out. It now shows the option's text (its label, or "Item <n>"
  when it has none), followed by any "Other" text.
- `reconcile --direction postgres->mongo` checks a copy it inserted into Mongo again once it has
  landed, and removes it when the record was deleted meanwhile (its tombstone, or the Postgres row
  gone), so a delete racing that insert can no longer bring the record back in Mongo.
- Expired deletion tombstones are pruned after a delete has committed, in a transaction of their own,
  instead of inside the delete's transaction, so a delete never waits on pruning or holds its locks,
  and a failed prune never undoes a delete.
- `reconcile --direction postgres->mongo` refuses to run unless every group it covers is on
  `DB_WRITE_MODE=postgres_primary_dual` (`--dry-run` excepted): under `dual`, Mongo deletes first and
  records no tombstone for a document that is not there, so a delete racing its Mongo insert would
  not be caught. When reconcile's removal of its own copy finds nothing left to remove, it says so
  in the log.

## [4.0.7] - 2026-10-25

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **No migrations and no compose or setting change.** The new deletion-request fields (`declined`
  status, closures, decline reason) are stored on the request document.
- **Rollback limit.** A 4.0.6 image can't read a deletion request that was declined: its status
  list has only `pending` and `success`, so loading one fails, and its respondent card would show it
  as deleted. Before rolling back, check (read-only) that no request was declined:

  ```sql
  SELECT count(*) FROM app.responses_deletion_requests WHERE status = 'declined';
  ```

  ```js
  db.responses_deletion_requests.countDocuments({status: "declined"})
  ```

  If either is above 0, fix forward on 4.0.7 instead of rolling back.
- **After the deploy:** to use the production smoke test, create a new API key for the test workspace
  that includes the new `forms:delete` scope, and replace `SMOKE_API_KEY` in its environment.

### Added

- Staff with `privacy.manage` close a pending deletion request by hand, without the form's provider:
  `POST /workspaces/{id}/forms/{form_id}/submissions/{response_id}/deletion-request/close` with
  `outcome` `completed` (the workspace's stored copy is deleted) or `declined` plus a reason from a fixed list.
  Responses imported from Google Forms could only be cleared by deleting them at the source and syncing again.
  Who closed a request and when is kept on it (every close is appended, never overwritten), and a later sync no
  longer brings back a response whose deletion request was completed. `completed` is refused (409) while a copy
  of the response that the workspace may own cannot be attributed to it. Respondents see a declined request as
  "Not deleted: <reason>" (English and Dutch), never as deleted.
- Public API: `DELETE /forms/{formId}` deletes a form and its responses. It needs the new key
  scope `forms:delete` ("Delete forms" when creating a key; `forms:write` does not allow it, so no
  existing key gains it) and a key creator with `form.delete`.
  `POST /forms/{formId}/responses/{responseId}/deletion-request/close` closes a pending deletion
  request as `completed` or `declined` with a fixed reason (`deletion_requests:write`; the creator
  needs `privacy.manage`).

## [4.0.6] - 2026-10-24

### Upgrade notes

- **Back up first.** Take a backup of Postgres and of Mongo right before the deploy.
- **Migrations run on start** (`deploy.sh`, or `DB_AUTO_MIGRATE`): app `0019`, `0020` and `0021`,
  auth `0004`, google `0004`. All are expand-only. `0019` refuses to run while
  `app.workspace_forms` holds duplicate (`workspace_id`, `form_id`) links; the read-only check is in
  the `0019` entry below.
- **No compose or setting change.**
- **Rollback limit.** Roll back the image only and keep the schema: a 4.0.5 image runs on the newer
  schema, so don't run the Alembic downgrades. Once two workspaces hold a deletion request for the
  same response, a 4.0.5 service using Mongo can't rebuild its old unique index on
  `responses_deletion_requests` (`form_id_1_response_id_1_provider_1`) and doesn't start, and the
  `0020` downgrade fails. Check first (read-only):

  ```sql
  SELECT form_id, response_id, provider, count(*) AS requests,
         array_agg(id ORDER BY updated_at DESC) AS ids
    FROM app.responses_deletion_requests
   GROUP BY form_id, response_id, provider HAVING count(*) > 1;
  ```

  ```js
  db.responses_deletion_requests.aggregate([
    {$group: {_id: {f: "$form_id", r: "$response_id", p: "$provider"}, n: {$sum: 1},
              ids: {$push: "$_id"}, workspaces: {$push: "$workspace_id"}}},
    {$match: {n: {$gt: 1}}}])
  ```

  If either finds a pair, prefer fixing forward on 4.0.6. To roll back anyway, merge each pair
  into one request in both stores first: note the ids and workspaces, complete the requests that
  can be completed, keep one request per response, and delete the others by id
  (`DELETE FROM app.responses_deletion_requests WHERE id = '<id>';` and
  `db.responses_deletion_requests.deleteOne({_id: ObjectId("<id>")})`). After upgrading again,
  re-file the removed requests in their workspaces.
- **After the deploy**, open the admin portal's health page. Every instance should report, with no
  mirror failures and no outbox backlog.

### Changed

- A form is linked to a workspace once: (`workspace_id`, `form_id`) is unique in `workspace_forms`, in
  Postgres (app revision `0019`, replacing the plain index) and in Mongo (`uq_workspace_forms_workspace_form`,
  built at startup while Mongo is used; links without a workspace or form are left out, as Postgres treats
  NULLs as distinct). Saving a link that already exists (another importer, two imports racing) returns
  the existing link unchanged instead of adding a second one. Existing duplicates are never merged
  automatically: the migration refuses before changing anything, naming the counts; a Mongo database
  holding duplicates still starts, without the index, and logs an error with the number of duplicate
  pairs. Check before upgrading (read-only): in Postgres `SELECT workspace_id, form_id, count(*),
  array_agg(id) FROM app.workspace_forms WHERE workspace_id IS NOT NULL AND form_id IS NOT NULL GROUP BY
  workspace_id, form_id HAVING count(*) > 1;`, in Mongo
  `db.workspace_forms.aggregate([{$group: {_id: {w: "$workspace_id", f: "$form_id"}, n: {$sum: 1}, ids:
  {$push: "$_id"}}}, {$match: {n: {$gt: 1}}}])`; keep one link per pair, in both stores.
- Deletion requests are per workspace. A provider response imported into two workspaces is stored once in
  each, and each workspace now files, sees and completes its own deletion request for its copy: a request
  filed in one workspace no longer refuses the other's, and no longer shows as the status of the other
  workspace's copy or in its responders' counts. The unique key becomes (`form_id`, `response_id`,
  `provider`, `workspace_id`): app revision `0020` in Postgres (nulls not distinct, replacing the
  per-response constraint) and `uq_deletion_requests_form_response_provider_workspace` in Mongo, built at
  startup while Mongo is used, where the old `form_id_1_response_id_1_provider_1` index is dropped at the
  same time (a failure of either is logged and the service starts anyway). Filing twice for the same copy
  is refused as before, and a request stored before requests carried a workspace is still found for the
  response.
- Changelog entries are now files in `changelog.d/` (`<pr-number-or-branch-slug>.<category>.md`)
  instead of edits to `CHANGELOG.md`, which a release assembles them into with
  `.github/scripts/changelog.py assemble X.Y.Z` (`--draft` previews). A PR check fails when a pull
  request changes code without a fragment (unless it is labelled `no-changelog`) or edits
  `CHANGELOG.md` outside a `docs/changelog-X.Y.Z` release branch. See `changelog.d/README.md`.

### Fixed

- Two writes to the same document at once, in `dual` or `postgres_primary_dual`, could reach the
  mirror store in the opposite order and leave it with the older version. After its mirror write,
  each write now brings the mirror's copy of the rows it touched in line with the primary's
  (counted as `mirror_repairs`); a mirror copy of a row the primary deleted is removed even when
  the rounds or the mirror timeout run out. `reconcile` no longer overwrites, or re-inserts, a copy
  the application changed or deleted after reconcile read it (counted as `skipped`, and the outbox
  stays open).
- `reconcile` could bring back a record deleted in one store whose delete had failed in the other
  (a response, a deletion request, an account). Every delete now records a tombstone (collection,
  id and time only) in the store that deletes, in every write mode. `reconcile` never copies a
  deleted record and deletes its surviving copy instead, in both directions, and `verify` reports
  deleted records that are still present (`tombstoned`). Tombstones are kept 120 days. New table
  `deletion_tombstones` in the `app`, `auth` and `google` schemas (app revision `0021`, auth and
  google `0004`).

## [4.0.5] - 2026-10-24

### Fixed

- The admin portal no longer shifts sideways when a page becomes long enough to scroll: every page reserves the
  scrollbar's width (`scrollbar-gutter: stable`), so the content stays put on short pages, long pages and after
  HTMX swaps or task progress updates.
- Importing from Google Forms works again after Google's consent screen. The Google Forms service sent a PKCE
  challenge with the authorization URL (the default of google-auth-oauthlib since 1.3) but exchanged the code
  without its verifier, so Google refused the exchange (`invalid_grant`). The verifier is now derived from the
  request's state with a server-side key, so the callback presents the matching one.
- The Google Forms service no longer depends on `OAUTHLIB_RELAX_TOKEN_SCOPE` in its environment: it relaxes
  oauthlib's scope comparison itself (Google always returns aliases and earlier grants) and instead checks that
  the scopes the import needs were granted, refusing with a clear message when the user unticked one.
  `invalid_client` and other OAuth errors from Google now answer with a message instead of a server error, and a
  callback whose state does not decrypt is refused before the code is used.
- Errors from a form provider service now reach the user with that service's own status and message (an expired
  authorization, a missing permission) instead of "Could not fetch data from proxy server."; the API logs the
  upstream status and error code.
- After the consent screen, an import that started without a `Referer` returns to the workspace's forms page
  instead of failing, and the picker flag is added to the return URL as a proper query parameter.

## [4.0.4] - 2026-10-24

### Added

- The Postgres cutover runbook (`docs/postgres-cutover-runbook.md`) now covers Docker Swarm stacks,
  which have no `deploy.sh`. For each stage (Stage 0, each group's read and primary switch, the jobs
  flips, stopping Mongo writes, turning Mongo off and decommissioning) it gives the environment
  changes per service, the order of the redeploys, what to watch, the soak and exit criteria, and
  the rollback. It also says how to run the migration CLI as a one-off on the stack, and covers the
  keyset freeze and the backup and restore test to do before Mongo is turned off.

### Changed

- Once every repository group is on Postgres for reads and writes (`DB_READ_SOURCE=postgres`,
  `DB_WRITE_MODE=postgres`, no group override back to Mongo, no shadow reads), the backend, its job worker,
  auth and the Google Forms service start and serve without MongoDB: no connection is made, `MONGO_URI` may be
  unset, and the backend's persistence status reports Mongo as "not used". While any group still uses Mongo,
  startup is unchanged and fails on an unreachable Mongo. CI's Postgres runs now go without a Mongo server.

- The dashboard sidebar's Workspace group is now Members, Themes, Single sign-on and AI. Single sign-on
  holds the Single sign-on and Domains tabs (only Domains, named so, when single sign-on is off on the
  instance); AI holds the Profile, Memory, MCP (endpoint and API keys) and Settings tabs, each shown only
  to members who may use it, and opens on the first of them. Every tab has its own address
  (`/dashboard/sso/domains`, `/dashboard/ai/memory`, ...); the old addresses (`/ai-settings`,
  `/ai-profile`, `/ai-memory`, `/api-keys`, `/domains`) redirect permanently. Members, Single sign-on
  and AI share one tab bar: a named navigation of links marking the current tab with
  `aria-current="page"`, with 44px targets, a visible focus ring, and sideways scrolling on small screens.
- The bettercollected logo is now the name alone, as the admin portal sets it: "bettercollected" in
  Instrument Sans 600, in ink, with no blue "b" and no trailing dot. The small mark, the favicon and the
  app icons are the same ink "b" (on a white square for the icons). The wordmark is labelled
  "bettercollected" for screen readers, and email logos now say "bettercollected" instead of "logo".

### Fixed

- A document import running in the API process that stops on an unexpected error (outside the import's
  own error handling, such as a database error while failing it) now fails the import with code
  `failed` and removes its empty draft, instead of leaving it running until it expires. Its task no longer
  ends with an exception nobody retrieves, which asyncio logged later with the whole traceback.
- Form builder: "Add Option" puts the cursor in the new option. The Flow view no longer opens by itself
  when a form gets its first logic while being edited (forms that already branch still open in it).
  Renaming a form titles its welcome page in the same undo step, and autosave no longer rewrites the
  welcome page's title on every save; the outline's Welcome row shows the form's title.
- Flow view: a page node's "+N more" counts only the questions it does not show (it counted one too
  many, the question that names the node). "Start with AI" opens on phones and small tablets too
  (its dialog fits a 375px screen); only "Create New Form" is marked desktop-only.
- The forms list and form search ask the auth service about each importer once, instead of once per
  form on the page. Search now shows each form's own importer: it could show another member's name on
  a form, and no importer at all on forms imported by someone other than the searching member. The forms
  list's response counts count distinct workspaces in MongoDB as Postgres does, so a form linked twice
  to the same workspace still counts that workspace's older responses.

### Security

- Searching a workspace's draft forms (`POST /workspaces/{id}/forms/search` without `published=true`)
  now needs permission to read the workspace's forms, as the forms list already did. Any signed-in
  account got 403 from the list but could search another workspace's drafts. Importer details (the
  importing member's name and email) are only ever attached for members who may read the workspace's
  forms: never in published search, and no longer when a non-member reads a single form. A single form's
  importer is now the member who imported it, not the first user the auth service returned.
- Reading one unpublished form (`GET /workspaces/{id}/forms/{form_id}` without `published=true`, by id
  or custom URL) now needs permission to read the workspace's forms, as the forms list and search do;
  anyone else gets 403, the same answer whether or not the form exists. `published=true&draft=true`
  falls back to a never-published form's draft for those members only; for everyone else it reads the
  published form, as `published=true` does. Published forms stay readable by anyone, as before.

## [4.0.3] - 2026-10-24

### Added

- The dashboard sidebar shows the running version under "Powered by bettercollected": the release
  tag on release builds (`v4.0.3`), `dev · <short sha>` or `staging · <short sha>` on builds from
  `develop` and `master`, and nothing on builds without the value. It is set when the webapp image
  is built (`NEXT_PUBLIC_APP_VERSION`; `scripts/app-version.sh` for self-built images) and is never
  shown on respondent pages.

### Fixed

- The Google Forms integration no longer fails to start with "MASTER_ENCRYPTION_KEYSET is set
  neither in the environment nor in the settings store" when the response keyset is held only in
  the settings store (after `bootstrap-keys` or `settings-prune`). The shared response cipher
  (`common.services.crypto_service`) was built when the module was imported, which could happen
  before the service had loaded its settings snapshot; it is now built on first use, so the import
  order no longer matters. The backend, its jobs worker and the integration still build it at
  startup and refuse to start when no keyset exists in either place.

## [4.0.2] - 2026-10-24

Groundwork for running on Postgres only (4.1): every write now reaches both data stores through
the routed repositories, the two copies of a mirrored write are identical, and operators get the
tools to verify and switch the stores group by group.

### Added

- `keyset.drop_old` has a `mongo_retired` parameter (off by default): a signed, audited statement
  that no service writes Mongo any more. Only then does it scan Postgres alone, and only when the
  task runner's `DB_WRITE_MODE*` say `postgres` for every group and every running backend and
  Google integration instance reports writing Postgres alone. Without it, both Mongo and Postgres
  must be configured and are scanned, as before.
- Services report the data stores they write in their settings heartbeat (admin revision 0018,
  `settings.service_state.write_stores`; the previous `report_state` signature keeps working).
- The migration commands (`python -m backend.migrate`, `auth.migrate`, `googleform.migrate`) record
  a "migration verified" marker after a fully clean `verify` (app revision 0017, auth 0003, google
  0003, table `store_migration`). `--group <name>` limits backfill, verify and reconcile to one
  repository group, and `status --json` gives counts per store, outbox depth, mirror failures, the
  last clean verify and the marker.
- Golden fixtures pin the exact bytes of every document stored in Postgres, and parity tests now
  cover the actions and AI repositories.
- A unique `(workspace_id, user_id)` index on `ai_preference_memories` in Postgres, as Mongo already
  has (app revision 0018). **Upgrade note:** the migration refuses to run while duplicate pairs
  exist and reports their number only; the cutover runbook shows how to find and resolve them.

### Changed

- **Upgrade note:** the admin tasks' `stores: auto` (`keyset.reencrypt`, `keyset.verify`,
  `responses.check_undecryptable`, `responses.backfill_workspaces`) now covers every store the
  services still write, from the task runner's `DB_WRITE_MODE`, `DB_WRITE_MODE__RESPONSES` and
  `DB_WRITE_MODE__GOOGLE` (root `.env`), plus any other configured store. With no write mode set
  it refuses with `write_mode_unknown`, and so does `keyset.drop_old`: set `DB_WRITE_MODE=mongo`
  (or the services' actual mode) in the root `.env`. Naming the stores (`mongo`, `postgres`,
  `both`) still works without it.
- `python -m backend.migrate jobs-sweep`, `python -m backend.custom_domain` and
  `python -m backend.membership_duplicates` read through the routed repositories: they follow
  `DB_READ_SOURCE` / `DB_WRITE_MODE` and open Mongo only while a group they use still needs it.
- On groups where Postgres is the primary store, saves move `updated_at` the way Mongo saves always
  have.
- The break-glass script `scripts/rotate_response_keyset.py` follows the same store rule as the
  keyset tasks: `drop-old` needs both stores configured unless `--mongo-retired` is given, which is
  refused unless every write mode is `postgres`.
- Pull-request checks run the Postgres mode in parallel shards (a few minutes became about two);
  every push to `develop`, a nightly run and a manual run test all suites in every storage mode.

### Removed

- Unused code: the old provider plugin loader, the scheduled re-import of Google Forms (nothing
  scheduled it) and its Temporal route and worker activity, the unused Google form and response
  caches, auth's unused providers repository, unused webapp provider APIs and strings, and the
  setting `TEMPORAL_ADD_IMPORT_SCHEDULES`. No table was dropped.

### Fixed

- Writes that went straight to Mongo now go through the routed repositories, so Postgres sees them
  in the dual-write modes: the sign-in code of an existing user, the name update after sign-in,
  Stripe checkout and plan changes, workspace responder updates, AI form prompts, price suggestions
  and the flow-template seed. A test now fails on any new direct database call outside the
  repositories.
- A mirrored write stores exactly what the primary wrote: one clock reading per write, an exact
  replay into Mongo, and Postgres saves that move `updated_at` like Mongo's. `verify` is clean right
  after a write in both dual-write modes.
- `verify` and `reconcile --direction postgres->mongo` no longer miss rows that exist only in
  Postgres between batches.
- Postgres twins: workspace action credentials are stored like Mongo's, and `update_proposal`
  updates every matching record and reports changes like Mongo.
- Aware datetimes with a non-UTC offset are stored as the UTC instant, so their checksum matches
  the Mongo copy.
- Tests no longer use generated secrets as test names, and a check keeps key-like strings out of
  the recorded test durations.

### Security

- Dependency updates for published advisories: Pillow 13.0.0 (backend, including the PDF import and
  its sandbox), pypdf 6.21.2, certifi 2026.10.19 (all Python services; 2026.10.23 in the Python SDK),
  OpenTelemetry API 1.45.1, filelock 4.2.4 and virtualenv 21.14.13 (auth and the Google integration),
  setuptools 84.1.0, black 26.10.1 (SDK development) and zod 4.6.7 (webapp tooling).
  **Upgrade note:** backend, auth and the Google integration now require Python 3.11 or newer
  (Pillow 13 and the patched filelock no longer support 3.10); the Docker images already use 3.11.

## [4.0.1] - 2026-10-19

### Fixed

- The Google Forms integration reports the response keyset's fingerprint in its settings
  heartbeat (it reported the master key's). The keyset tasks in the admin portal
  (`keyset.promote`, `keyset.reencrypt`, `keyset.drop_old`) no longer refuse with
  `consumer_missing_key` on a stack that runs the integration.
- The admin service's own warnings (refused gate requests, mail that could not be sent)
  reach the container log.

### Changed

- Dependency updates: webapp minor and patch releases; CI actions `schemathesis/action`
  3.0.0 and `astral-sh/setup-uv` 10.3.0.

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
- `.env.deployment` is no longer tracked: the repository ships `.env.deployment.example`,
  and `deploy.sh` creates `.env.deployment` from it (mode 600) only when it is missing.
  **Copy your `.env.deployment` before you pull** (`cp -p .env.deployment .env.deployment.mine`):
  the pull deletes an unchanged copy without a warning (it holds the values 3.x shipped,
  including the published keyset, which a stack whose responses are encrypted with it needs
  for the import) and refuses to run while the file has local changes. Undo those
  (`git checkout -- .env.deployment`), pull, then put your copy back
  (`mv .env.deployment.mine .env.deployment`); git ignores it from now on. Details:
  [Upgrading to 4.0](docs/admin-service.md#upgrading-to-40), "Before you start".
- The deploy workflow still deploys `develop` and `master` to the development and staging
  stacks; only production is deployed from release tags (`vX.Y.Z`).
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

- **Found by running the real `deploy.sh` end to end** (`scripts/v4-compose-check.sh`):
  `deploy.sh` runs on a host that has only the Docker Compose plugin (`docker compose`;
  it looked the two words up as one command and did nothing there); a new install starts
  without an Unsplash access key the backend never reads; the Postgres containers are
  checked over TCP with a start period, so `deploy.sh` no longer races the image's
  temporary first-run server; nginx waits for the webapp and restarts; the jobs worker
  and the task runner no longer inherit the backend image's health check (they were
  reported unhealthy for good); `responses.check_undecryptable` and
  `responses.backfill_workspaces` read the keyset from the settings store first, as the
  documentation says (they refused with `keyset_missing` on every 4.0 stack).
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
- Upgrading from 3.4.0: the first run of the admin roles script no longer fails (it grants
  only the columns that exist before the application migrations; the second run adds the
  rest), and a service whose response keyset is only in the settings store reads it from
  there instead of failing at start (an environment value still wins).

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
  `OAUTHLIB_INSECURE_TRANSPORT` is no longer set in the shipped env template. The deploy
  workflow pins its actions by commit; `develop` and `master` still deploy to the
  development and staging stacks, and only production is deployed from release tags
  (`vX.Y.Z`), refusing any other tag name. `.env.deployment` is no longer tracked: the
  repository ships `.env.deployment.example`, from which `deploy.sh` creates a missing
  `.env.deployment` (mode 600, never overwriting one), and the compose file treats it as
  optional, so `docker compose config` works on a fresh checkout.
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

[Unreleased]: https://github.com/bettercollected/bettercollected/compare/v4.0.13...HEAD
[4.0.13]: https://github.com/bettercollected/bettercollected/compare/v4.0.12...v4.0.13
[4.0.12]: https://github.com/bettercollected/bettercollected/compare/v4.0.11...v4.0.12
[4.0.11]: https://github.com/bettercollected/bettercollected/compare/v4.0.10...v4.0.11
[4.0.10]: https://github.com/bettercollected/bettercollected/compare/v4.0.9...v4.0.10
[4.0.9]: https://github.com/bettercollected/bettercollected/compare/v4.0.8...v4.0.9
[4.0.8]: https://github.com/bettercollected/bettercollected/compare/v4.0.7...v4.0.8
[4.0.7]: https://github.com/bettercollected/bettercollected/compare/v4.0.6...v4.0.7
[4.0.6]: https://github.com/bettercollected/bettercollected/compare/v4.0.5...v4.0.6
[4.0.3]: https://github.com/bettercollected/bettercollected/compare/v4.0.2...v4.0.3
[4.0.2]: https://github.com/bettercollected/bettercollected/compare/v4.0.1...v4.0.2
[4.0.1]: https://github.com/bettercollected/bettercollected/compare/v4.0.0...v4.0.1
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
