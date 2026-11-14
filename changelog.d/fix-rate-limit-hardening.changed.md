- The per-client rate limits are now live settings (0 turns one off, no restart):
  `API_CODE_MAIL_PER_CLIENT_PER_HOUR` (sign-in code mails per client, now 60 an hour
  instead of 10), `API_CODE_MAIL_PER_ADDRESS_PER_HOUR` (per mailbox, 3 an hour) and
  `API_SUBMIT_PER_CLIENT_FORM_PER_MINUTE` (response submits per client and form, 30 a
  minute). An IPv6 client is now counted by its /64 (one subscriber or device) instead
  of its /48, so the phones of one mobile carrier no longer share a budget.
  Upgrade notes: an organisation whose people reach the internet through one address
  shares that client's 60 code mails an hour; raise `API_CODE_MAIL_PER_CLIENT_PER_HOUR`
  if a whole group signs in at once. A person who asks for a fourth sign-in code within
  an hour for the same mailbox (spelling variants count as one) is refused until the hour
  ends, and `API_CODE_MAIL_PER_ADDRESS_PER_HOUR` changes that. Breaker runbook: if the
  instance-wide breaker trips and sign-in stops for everyone, set
  `API_CODE_MAIL_PER_HOUR=0` to restore sign-in while blocking the source at the proxy.
  The client limits only work when `API_TRUSTED_PROXIES` (alias `TRUSTED_PROXIES`)
  lists the reverse proxy the API sees; unset or wrong, they are off.
