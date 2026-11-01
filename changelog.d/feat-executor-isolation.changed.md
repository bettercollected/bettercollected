- **Upgrade note for the actions executor:** a webhook, Slack or Discord address that is private or not https, or a
  workspace SMTP server that is internal, is now refused; list such hosts in `ACTION_EGRESS_ALLOW` on the executor if
  that is deliberate. Custom action code no longer has `type`, `str.format`, `fetch_oauth_token` or
  `build_google_service`, and `get_secret()` returns a handle to pass to a call rather than the value. Once the backend
  and the executor are both upgraded, remove `AES_HEX_KEY` from the executor service. `ACTION_ISOLATION=legacy` restores
  the previous in-process run.
