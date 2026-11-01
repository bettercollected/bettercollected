# temporal/AGENTS.md

Scoped guidance for the **background workers**. Read the root [../AGENTS.md](../AGENTS.md) first.

## Role

Durable / long-running work that must not block backend request handlers runs here as **Temporal** workflows. The
backend (`services/temporal_service.py`) starts workflows and creates Schedules on the Temporal server (PostgreSQL-backed
`temporalio/auto-setup` image); these three worker services execute them.

## Three independent workers

Each is a standalone Python service with its own `main.py`, `requirements.txt`, `Dockerfile`, `run.sh`, and
`activities/ workflows/ models/ settings/ wrappers/` layout. **Not Poetry** — plain venv + `requirements.txt`.

| Dir | Workflows | Activities | Purpose |
|---|---|---|---|
| [worker/](worker/) | `DeleteResponseWorkflow`, `DeleteUserWorkflow`, `SaveTemplatePreview` | `delete_response`, `delete_user`, `save_preview`, `get_preview_image` | GDPR-style response/user deletion; template preview screenshots (Selenium/Chrome) |
| [csv-worker/](csv-worker/) | `ExportCSVWorkflow` | `export_as_csv` | Export form responses to CSV |
| [actions-executor/](actions-executor/) | `RunActionCode` | `run_action_code` | Execute user-defined form-action / automation code |

## The actions executor on the Postgres queue (default)

`actions-executor/main.py` follows `JOBS_BACKEND` (default `postgres`): `procrastinate_worker.py` consumes the
`actions` queue as the `bc_jobs_exec` role (`DATABASE_URL`). The role sees only the `actions` queue's rows and writes
only `run_action` rows with `action_` locks; it cannot write the events or periodic-defers tables. The executor
refuses to start where the backend has not applied that (`utilities/queue_isolation.py`: policy, no superuser or
bypass or table ownership, no write on those tables, no TEMPORARY on the database and no role membership for it, a minimal
`bc_jobs_def`, SECURITY DEFINER triggers; `postgres/ensure-jobs-exec-role.sh` itself revokes TEMPORARY from PUBLIC). The job carries **ids and a run
token only**; `utilities/run_context.py` fetches the run's data from the backend's in-network route when it runs,
presenting the job's `run_token` (the route also checks the job is `doing`; the job key alone reads nothing; 410 =
the run no longer applies or is over a day old, skipped). Three runs at most (waits of 5 s and 25 s), cut off after
90 s; a failure names ids and the error's class, never its message (it can hold an answer); the job's result is one
word; `utilities/job_logging.py` keeps job arguments out of procrastinate's log lines. Jobs queued by 4.1.x with the
whole run in them are still run once (and `python -m backend.jobs.schema` scrubs them). Tests:
`tests/test_run_job.py`, `tests/test_queue_isolation.py`, `tests/test_job_logging.py`. The start check also verifies each
SECURITY DEFINER function of the queue's schema: owner `bc_jobs_def` (NOLOGIN) and `search_path` ending in `pg_temp`
(procrastinate's `CREATE OR REPLACE FUNCTION` resets both: the check fails closed until `python -m backend.jobs.schema`
runs again). `JOBS_BACKEND=temporal` runs the
workflow below instead.

**Isolation** (`ACTION_ISOLATION=enforce`, the default; `docs/executor-isolation.md`): custom action code (only a platform
admin can create it; creators set parameters and secrets, never code) runs in one confined child per run
(`sandbox/`: `policy.py` AST refusal, `confine.py` Landlock + seccomp + `no_new_privs` + rlimits + chroot/uid drop when
root, `child.py`, `broker.py` which refuses a child that did not confine itself and answers its calls from the table
built in `utilities/custom_action.py`). The child gets no secret value (handles the broker substitutes), no environment, no
file, no socket. Every outgoing call (built-in actions too) goes through `utilities/egress.py` (https/443, every resolved
address public, connect to the checked address, no redirects; the action's own parameters and `ACTION_EGRESS_ALLOW` are the
only exceptions); a workspace's SMTP server is checked the same way. The executor asks the backend for the run's secrets
**opened** (`{"secrets": "plain"}`, `secrets_plain` in the answer), so it needs no `AES_HEX_KEY` (`configs/cipher.py` builds
the cipher only when a sealed value shows up: the Temporal path, or a backend older than 4.3); a refreshed Google credential
goes back in plain over the run-scoped `PATCH .../runs/{r}/secrets`. `configs/crypto.py` stays an identical copy of the
worker's (`common/tests/test_key_ring.py`). Tests: `tests/test_sandbox_adversarial_process.py` (policy layer off, the process
must hold), `test_sandbox_adversarial_language.py`, `test_custom_action.py`, `test_egress.py`, `test_action_isolation.py`; the
process tests skip only where the kernel cannot confine a child. Add a name to the child's namespace only with a handler
that checks its arguments against this run; never hand it a live object (a function's `__globals__` is the whole process).
Mail from custom code: the code gives the subject and recipients only; the broker builds the SMTP group itself (`prepare_mail`), derives the copy kind from the recipient and sends through `utilities/pinned_mail.py` (connect to the checked address, hand the socket to aiosmtplib). Built-in sends, name lookups and slow calls run off the event loop (`blocking()`), custom-code calls on `custom_action.call_pool`. A secret stored on the action itself only goes to the exact address (scheme, host, port, path, query) in the action's own parameters (`egress.trusted_urls_of`; not the operator's allow list), and its reply is not shown to the code. `ACTION_EXECUTOR_KEY_ALLOWED=false` makes the executor refuse to start under `enforce` while `AES_HEX_KEY` is set (`settings.application.refuse_key_when_not_allowed`). Only the executor's own Google call (never the code's say-so) switches an action off. The image runs as a non-root user (Landlock); root with `cap_drop: ALL` is not supported. `ACTION_ISOLATION=legacy` is the old in-process `exec`, a way back only (error at start, warning per run).

## Tech

`temporalio==1.2.0`, **`pydantic==1.10.9`** (note: v1, unlike some other services), `httpx`/`requests`,
`selenium==4.14.0` (worker only, for previews), `cryptography`, `elastic-apm` + `ecs-logging`, `python-dotenv`.

## How a worker starts

`main.py` → `asyncio.run(main())` → `Client.connect(settings.temporal_server_url, namespace=...)` →
`Worker(client, task_queue=..., workflows=[...], activities=[...])` → `.run()`, spawning `settings.workers` workers.
Launched via each service's `run.sh` (activates `venv`, runs `python3.10 main.py`) or its Dockerfile.

## Adding / changing work

1. Write the activity in `activities/` (the actual side-effecting code — HTTP calls, DB, Selenium, etc.).
2. Write/extend the workflow in `workflows/` (orchestration only — deterministic; no I/O directly in workflow code,
   call activities for that).
3. Register both in the worker's `main.py` (`workflows=[...]`, `activities=[...]`).
4. Trigger it from the backend via `services/temporal_service.py` (start workflow or create a Schedule) using the
   matching **task queue name** — the backend and the worker must agree on task queue + workflow name.

## Run / test

```bash
cd temporal/worker            # (or csv-worker / actions-executor)
python3.10 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
./run.sh                      # connects to TEMPORAL_SERVER_URL and starts the worker
```
Requires a running Temporal server — locally via `docker-compose.deployment.yml` (`temporal` + `postgresql` services)
or a standalone Temporal dev server. Set `TEMPORAL_SERVER_URL` / `TEMPORAL_NAMESPACE` in env.

## Gotchas

- **Workflow determinism:** never do I/O, randomness, or wall-clock reads directly in workflow code — always through
  activities. Non-determinism breaks Temporal replay.
- **Task-queue / name contract:** the workflow name and task queue used by the backend must exactly match what the
  worker registers, or jobs sit unpicked. Change both sides together.
- **Selenium worker** needs a Chrome/Chromedriver runtime (baked into its Dockerfile) — preview generation fails without it.
- **Pydantic v1 here** vs newer Pydantic elsewhere — don't copy v2-only patterns into these services.
- **`API_KEY`** (the `api-key` header on every call to the backend) must equal the backend's
  `TEMPORAL_API_KEY`. It has no default: unset or the old `random_api_key` becomes `""`
  (`settings/application.py`), the worker logs an error at startup and the backend answers 503.
- Encrypted user tokens (`models/user_tokens.py`) are decrypted only inside activities using the shared AES keysets —
  keep decrypted secrets out of logs and workflow history.
