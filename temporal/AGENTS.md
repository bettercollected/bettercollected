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
| [worker/](worker/) | `ImportFormWorkflow`, `DeleteResponseWorkflow`, `DeleteUserWorkflow`, `SaveTemplatePreview` | `import_form`, `delete_response`, `delete_user`, `save_preview`, `get_preview_image` | Provider form imports; GDPR-style response/user deletion; template preview screenshots (Selenium/Chrome) |
| [csv-worker/](csv-worker/) | `ExportCSVWorkflow` | `export_as_csv` | Export form responses to CSV |
| [actions-executor/](actions-executor/) | `RunActionCode` | `run_action_code` | Execute user-defined form-action / automation code |

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
- Encrypted user tokens (`models/user_tokens.py`) are decrypted only inside activities using the shared AES keysets —
  keep decrypted secrets out of logs and workflow history.
