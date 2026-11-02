- Hardening of form embedding before `FORM_EMBED_ENABLED` is turned on. A freshly started
  webapp whose first look-up of a workspace's allowed sites fails now serves its form pages
  with `frame-ancestors 'self'` and the dashboard when the webapp's own `FORM_EMBED_ENABLED`
  environment variable is on (it is passed through by the deployment compose file, default
  off), instead of no framing header at all; with it off or unset nothing changes, and
  whenever the backend answers its answer decides. The public policy route is rate limited
  (per client address and per workspace, 429 with `Retry-After`). The embed script is now a
  versioned file that never changes (`/embed/v1.js`, served immutable with CORS for any
  site), the share dialog's code pins it with `integrity` and `crossorigin`, and the Embed
  tab and `docs/embed.md` show a script-free iframe version and note the iframe `sandbox`
  attribute.
