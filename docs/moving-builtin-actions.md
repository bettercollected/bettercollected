# Moving built-in actions

Until 4.3 the built-in actions of a form (send a webhook, send to Slack, send to Discord, send me a copy, the respondent's copy,
Google Sheets) ran in the actions executor. From 4.4 the backend does them itself:

| Built-in action | Becomes |
|---|---|
| send a webhook | a [webhook](webhooks.md#formats) in the `legacy_list` format (the same body, now also signed) |
| send to Slack, send to Discord | a webhook in the `slack` or `discord` format (the same messages), only to their own addresses |
| send me a copy | an [email action](email-actions.md#actions-that-replaced-a-built-in-action) to that one address (a current member of the workspace), every question |
| the respondent's copy | an email action with the respondent's copy on, every question |
| Google Sheets | stays an action; the backend's own runner appends the rows (queue `integrations`) |

They then use the delivery log, retries, limits and the respondent's privacy panel of webhooks and email actions, and appear in the form's Webhooks and Email actions settings.
The executor is left with custom actions only (written by a platform administrator); when none is in use it can be switched off.

A command, `python -m backend.migrate_builtins`, does the move, form by form, after you have looked at what it would do. Nothing moves by itself, and nothing is sent or switched on by the move.

## What changes for people

- **Webhooks, Slack, Discord:** the same bodies. A webhook's address must be a public https address on port 443 (a migrated address that is http, internal or on another port is **not** moved: it is reported and
  stays with the executor). Slack and Discord addresses must be on their own hosts. A webhook receiver now also gets signature headers (extra headers; nothing that read the body breaks).
  Slack text values are escaped (`&`, `<`, `>`).
- **Mails:** plain text instead of the old HTML look, the instance's mail server instead of a server set on the action, a copy to a signed-in respondent with a verified email only, a team copy to a member of the workspace only.
  A server (SMTP) set on a workspace or form is dropped and counted in the report. A question added to the form later **is** in the mail (`allQuestions`).
- **Sheets:** the same rows and columns. A tab name containing `..` cannot be used (the run ends `sheet_title_unsupported`).
- **Limits:** a form can have 5 webhooks and 5 email actions; a form that would go over is not moved (reported).
- **Switches:** `WEBHOOKS_ENABLED` and `EMAIL_ACTIONS_ENABLED` must be on for what is switched on, and a mail server (`MAIL_*`) must be set for mail, or the command reports it and moves nothing of that kind.
  Turn them on first: a stack with them off would otherwise lose those deliveries.

## Before you start

1. **Upgrade to 4.4** (backend, jobs worker, webapp) with the executor as it is. The executor must be 4.3 or later (the key-only credential route of older executors is gone).
2. **The jobs worker must serve the `integrations` queue:** leave `JOBS_QUEUES` unset, or make it `default,webhooks,emails,exports,imports,integrations`. The worker logs a warning at start when it does not.
3. **Turn the switches on** (`WEBHOOKS_ENABLED=true`, `EMAIL_ACTIONS_ENABLED=true`) and check the mail settings, then restart the backend and the jobs worker.
4. Take a backup of the database (the move writes to the form documents, the webhook and email action tables).

Run the commands inside the backend image, as the application's database role, for example (the self-hosted compose file; use your own service name elsewhere):

```bash
docker compose -f docker-compose.deployment.yml exec backend python -m backend.migrate_builtins preflight
```

## The steps

### 1. Count what you have (read-only SQL)

```sql
-- built-in action entries on forms, per kind, and how many are on
SELECT a.doc->>'name' AS action, count(*) AS entries,
       count(*) FILTER (WHERE (e->>'enabled')::boolean) AS enabled
  FROM app.forms f
  CROSS JOIN LATERAL jsonb_array_elements(COALESCE(f.doc->'actions'->'on_submit','[]'::jsonb)) e
  JOIN app.actions a ON a.id::text = e->>'id'
 WHERE COALESCE((a.doc->>'predefined')::boolean,false)
 GROUP BY 1 ORDER BY 1;

-- actions with code of their own (these keep the executor), defined and attached to forms
SELECT count(*) AS defined FROM app.actions WHERE NOT COALESCE((doc->>'predefined')::boolean,false);
SELECT count(*) AS attached
  FROM app.forms f
  CROSS JOIN LATERAL jsonb_array_elements(COALESCE(f.doc->'actions'->'on_submit','[]'::jsonb)) e
  JOIN app.actions a ON a.id::text = e->>'id'
 WHERE NOT COALESCE((a.doc->>'predefined')::boolean,false);

-- runs waiting for the executor on the Postgres queue
SELECT status, count(*) FROM jobs.procrastinate_jobs WHERE queue_name='actions' GROUP BY 1;
```

### 2. `preflight`: what would move, what blocks it

```bash
python -m backend.migrate_builtins preflight            # all forms
python -m backend.migrate_builtins preflight --workspace <workspace id>
```

It prints counts as JSON (never an address, recipient or secret) and exits 0 only when nothing blocks. Read the keys:

- `found.<action>`, `movable.<action>`, `forms_with_builtins`;
- `blocked.<code>` (and `blocked.<code>.<action>`): `address_missing`, `address_invalid`, `address_not_allowed` (resolves to a private address), `address_unreachable`, `host_not_allowed`
  (Slack/Discord off their own address), `recipient_missing`, `recipient_not_member`, `cap_exceeded`, `switch_off`, `mail_not_configured`, `workspace_unavailable`, `temporal_unreachable`;
- `not_moved.disabled.<action>` (an action nobody had on that cannot move: left as it is), `skipped.form_v1` (forms of the first builder never ran their actions), `skipped.already_moved`, `dropped.mail_server`;
- `open_run_action_workflows` when the executor runs on Temporal (below).

What blocks is decided by you, case by case, never relaxed by the command: fix the address or the member, move the action by hand (a webhook or email action of your own), or leave it with the executor.
Run it again after each fix.

### 3. If the executor's runs are on Temporal: know what is open

`JOBS_BACKEND` says where the executor's `run_action` runs. On the Postgres queue the command looks at the queue itself (step 1's last query). **On Temporal it asks the Temporal server itself**
(through the backend's own `TEMPORAL_SERVER_URI`, `TEMPORAL_NAMESPACE` settings) for the open `run_action_code` workflows, in `preflight` (a count) and in `apply` (per form):

- `apply` moves a form only when it has **no open workflow**; a form with some is reported (`blocked.queued_runs`) and left for the next run. A workflow lives seconds to minutes, so draining is: apply, wait, apply again.
  `--wait-queue 120` makes `apply` wait up to two minutes per form for them to finish.
- A Temporal server the backend cannot reach (connection, login, no answer in 30 seconds) is **never** read as "nothing open": both commands report `blocked.temporal_unreachable`, move nothing, and exit with code 3.
  Fix the connection. Only if you know for certain that nothing is open, `--temporal-drained` skips the check; it logs a warning, shows as `temporal_check_skipped_by_operator` in the output, and is recorded on every action it moved
  (in the entry's `migrated_to` as `temporal_check` and in the webhook's change history).
- To look yourself: `temporal workflow list --query 'WorkflowType="run_action_code" AND ExecutionStatus="Running"'` (count only).
- Once a form is moved, new submissions start no workflow for its moved actions, so the open ones only run down.

### 4. `apply`

```bash
python -m backend.migrate_builtins apply --workspace <one workspace id> --wait-queue 120    # try one workspace first
python -m backend.migrate_builtins apply --wait-queue 120                                  # then the rest
```

Per form, in one transaction, the new webhooks and email actions are created (switched on only if the old action was), the old entry is switched off and marked, and the Sheets entry is marked for the backend.
It is safe to run again: what is moved is not moved twice. It exits 1 while anything is blocked (the rest is moved). New submissions are delivered by the new rows; a run that was already queued for the executor still completes there
and is not delivered twice.

### 5. `verify`

```bash
python -m backend.migrate_builtins verify
```

Every moved action has its target, the target opens (address and secret), is on exactly when the old action was, and the old entry is off. Exit 0 and no `problem.*` key.

### 6. Observe

Submit a test response to a migrated form and look at its **Deliveries** (webhooks and email actions) in the form's settings. A Sheets run is in the same action log (type `sheets`; `failed` with a code such as
`sheet_missing`, `oauth_token_missing`, `sheet_access_denied`). Expect no `action_run_not_queued` errors in the backend's log. Keep the executor for at least one release: **`rollback` is possible until you finalize**.

### 7. Executor to 0

When the delivery logs look right, no custom action is in use (step 1), `preflight` shows no open `run_action_code` workflows (or the Postgres queue is empty) and `verify` is clean:

```bash
python -m backend.migrate_builtins preflight     # nothing blocked, open_run_action_workflows 0 (Temporal)
docker service scale <stack>_<executor service>=0        # Docker Swarm; or: docker compose stop <executor service>
```

If a custom action is in use the executor stays (only for it). Removing the executor's service, its environment and its database role is a later release's cleanup, with its own steps.

## Giving it back

```bash
python -m backend.migrate_builtins rollback [--workspace <id>]
```

The old entries are switched on again as they were (and the Sheets mark removed), the moved webhooks and email actions are switched **off** and their rows and logs kept. It needs the executor to be running. Running `apply` again
finds the same rows (their ids are derived from the form and the action): none is added twice.

## Exit codes

`0` done and nothing blocked (`verify`: nothing wrong); `1` something is blocked or wrong; `2` usage; `3` Temporal could not be asked.
