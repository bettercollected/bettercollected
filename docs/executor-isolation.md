# Isolating the actions executor

The actions executor (`temporal/actions-executor`) runs the actions a form has switched on, when a response is
submitted. Two kinds of action run there:

- **built-in actions** (`send_webhook`, `send_to_slack`, `send_to_discord`, `responder_copy_mail`, `creator_copy_mail`,
  `integrate_google_sheets`): fixed code. What a form creator controls is their **settings**: a webhook address, an SMTP
  server, a spreadsheet id.
- **custom actions**: a platform administrator creates an action with its own Python code (`POST /actions`, which needs the
  platform `ADMIN` role). Creators and workspace members never write code: they attach an existing action to a form and fill
  in its parameters and secrets.

Since 4.3 both run under isolation by default (`ACTION_ISOLATION=enforce`). This page says what that means and what an
operator does. Design background and the test list are at the end.

## What a run can reach

| | Built-in action | Custom code |
|---|---|---|
| Outgoing calls | only through the egress rules below | only to a host **this run is configured with** (a parameter or secret of the action, the workspace or the form) or one the operator allows, and then through the egress rules |
| Keys, environment, files | none reached: the executor needs no encryption key | none: the code runs in a child process with an empty environment, no file access and no network |
| Secrets | opened by the backend for this one run and used inside the executor | the code holds a **handle** (`get_secret("Token")` prints `<secret Token>`); passing it in a call's headers, body or mail login makes the executor substitute the value |
| Other runs | none | none: one child per run, with only that run's data |
| Time and memory | the job's 90 s limit | per child: address space (`ACTION_SANDBOX_MEMORY_MB`), CPU (`ACTION_SANDBOX_CPU_SECONDS`), wall clock (`ACTION_SANDBOX_TIMEOUT_SECONDS`), number of calls (`ACTION_SANDBOX_MAX_CALLS`), log size |

### The egress rules (every outgoing call of an action)

- `https` only, port 443 only, no user name or password in the address, no IP address as the host in any spelling.
- The host is resolved at **every** call and **every** answer must be a public address (not private, loopback, link-local
  including cloud metadata addresses, carrier-grade NAT, multicast or reserved, nor any of those inside an IPv6 form).
  The connection goes to the address that was checked.
- No redirects, a capped request and reply, bounded time.
- A workspace's or form's own SMTP server must be a plain public host name on port 25, 465, 587 or 2525.
- Exceptions, both chosen by the operator and never by a creator: the addresses in the **action's own parameters** (the
  defaults set when the instance's administrators created the action, including the instance's SMTP settings), and the hosts
  listed in `ACTION_EGRESS_ALLOW`.

A webhook that used to point at a private or plain-http address is therefore refused; list its host (or `host:port`) in
`ACTION_EGRESS_ALLOW` on the executor if that is deliberate.

### Custom code

The code may use: the run's `form`, `response`, `workspace`, `action` (without any secret), `get_parameter(s)`,
`get_secret(s)` (handles), `get_simple_form_response()`, `get_state()`, `log()`/`print()`, `json.dumps/loads`, `random(seed)`,
`HTTPException`, a handful of builtins (`len`, `sum`, `sorted`, `range`, `str`, `int`, `list`, `dict` ...), and the calls
`send_data_webhook`, `send_data_discord`, `send_data_slack`, `config_mail` + `send_mail_action` (the SMTP settings must be
the configured ones; recipients are the respondent or a current member of the workspace, at most five),
`append_in_sheet` (a configured sheet, the run's own credential, at most 500 rows).

It may not: `import`, define classes, use `async`/`yield`, touch attributes starting with `_`, frame, generator, traceback
or code attributes, call `str.format` (use f-strings or `%`), or name `eval`, `exec`, `open`, `getattr`, `type`, `vars` and
the like. `fetch_oauth_token` and `build_google_service` are no longer available (use `append_in_sheet`). A refusal ends the
run with a message naming the line.

## How it holds (layers)

1. The code is parsed and refused if it names something that has ever been a way out of a restricted `exec`
   (`sandbox/policy.py`). This layer is **not** the boundary.
2. The code runs in one child process per run (`sandbox/child.py`, `sandbox/confine.py`). Before it reads any code the
   child closes every inherited file descriptor, sets resource limits, cuts itself off from the filesystem (Landlock with
   no access at all; plus `chroot` into an empty directory and a drop to an unprivileged user when it starts as root),
   sets `no_new_privs`, and installs a seccomp filter that denies sockets, `execve`, `fork`/`clone`, signals to other
   processes, `ptrace`, mounts and namespaces, user and key calls, every change to the filesystem and every write-open.
   These are Linux kernel features applied by the child to itself: nothing is needed from the container runtime, the
   orchestrator or the operator, on a compose stack, on Docker Swarm or on a bare host.
3. The executor (the **broker**, `sandbox/broker.py`) refuses to send code to a child that did not report all of that, answers
   the child's calls from a fixed table, enforces the quotas, and kills the child at the end. The executor process also
   makes itself non-dumpable, so its `/proc` entries are not readable by another process of its user.

A host the kernel cannot confine (no Landlock and not root: kernel before 5.13, rootless without the feature) runs built-in
actions as usual, and **refuses custom code**. The start log says which it is:
`action sandbox ready: filesystem=chroot+landlock seccomp=True unprivileged=True` or `action sandbox NOT available`.

## Operator steps

1. Upgrade the **backend** first. It adds the optional request `{"secrets": "plain"}` on the run's context route and a run-scoped
   route for a refreshed Google credential; nothing changes for an executor that has not been upgraded.
2. Upgrade the **executor** image. At start it logs the sandbox status (above).
3. Once the executor and the backend are both 4.3, **remove `AES_HEX_KEY` from the executor service**: the backend now opens the
   run's secrets, so the executor holds no encryption key. (While the backend is older, the executor still needs it and keeps
   working with it.)
4. Optionally list internal hosts your actions deliberately call in `ACTION_EGRESS_ALLOW`.
5. Keep the container as tight as your orchestrator allows (defence in depth, not relied on): a read-only root filesystem,
   `cap_drop: [ALL]` with a non-root user (the sandbox then uses Landlock alone), memory and CPU limits, an internal network with
   a route to the backend's internal listener, the job database and the public internet only. Docker Swarm stack files do not apply every
   option a compose file can (`network_mode`, a custom seccomp profile, `tmpfs`); nothing here depends on them.

`ACTION_ISOLATION=legacy` restores the pre-4.3 in-process run. It is a way back only: the code then runs inside the executor
process and can reach everything the process can. It logs an error at start.

## Settings (executor environment)

| Name | Default | Meaning |
|---|---|---|
| `ACTION_ISOLATION` | `enforce` | `enforce` or `legacy` |
| `ACTION_EGRESS_ALLOW` | empty | comma separated `host` or `host:port`: reachable although internal or not https |
| `ACTION_SANDBOX_MEMORY_MB` | 256 | address space of a custom-code child |
| `ACTION_SANDBOX_CPU_SECONDS` | 10 | CPU time of a child |
| `ACTION_SANDBOX_TIMEOUT_SECONDS` | 30 | wall clock of a run |
| `ACTION_SANDBOX_MAX_CALLS` | 20 | outside calls per run |

## Known limits

- The seccomp filter is a deny list. A permitted system call that has a kernel flaw is not stopped by it; the unprivileged
  user, the container's own default profile and a dedicated host are the answer for the most exposed setups.
- An SMTP server a workspace named is checked when the executor is about to connect, but the mail library resolves the name
  again; a name that changes its answer in between is not pinned. A network that cannot reach internal services closes that.
- Built-in actions run inside the executor process with that one action's secrets for the length of the run.
- Creator-authored code is not a feature; this isolation was built so that it could become one.

## Tests

`temporal/actions-executor/tests/test_sandbox_adversarial_process.py` (code with the parse layer switched off: environment,
files, network, processes, privileges, descriptors, other runs, CPU, memory, output), `test_sandbox_adversarial_language.py`
(the usual escapes, refused and leak-free), `test_custom_action.py` (every call and its refusals), `test_egress.py`
and `test_action_isolation.py` (addresses, pinning, redirects, the built-in actions against internal targets), and in the
backend `tests/app/jobs/test_action_run_secrets.py`. The process-level tests run the real child and skip only where the
kernel cannot confine one.
