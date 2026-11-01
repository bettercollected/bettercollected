- **The actions executor is isolated** (`ACTION_ISOLATION`, on by default). Custom action code now runs in a
  per-run child process that has no environment, files, network, keys or other runs' data (Landlock, seccomp,
  `no_new_privs`, resource limits), behind a broker that makes every outside call: only to hosts the run is
  configured with, and secrets are handles the code cannot read. Every outgoing call of an action (webhook, Slack,
  Discord, a workspace's SMTP server) follows one set of rules: https on port 443, public addresses only (checked at
  every call, connected to the address that was checked), no redirects. The executor no longer needs `AES_HEX_KEY`:
  the backend opens the run's secrets for it (new optional request `{"secrets": "plain"}` on the run's context route)
  and takes a refreshed Google credential back on a new run-scoped route, which seals it. See
  `docs/executor-isolation.md`.
