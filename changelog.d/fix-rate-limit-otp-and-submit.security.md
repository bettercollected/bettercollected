- Hardening: sign-in code mails (respondent and creator) are now rate limited per
  address (3 an hour, Gmail dots and `+tags` folded) and per client (60 an hour, IPv6
  by /64), with one instance-wide circuit breaker, `API_CODE_MAIL_PER_HOUR` (default
  20000 an hour, 0 turns it off, logged at ERROR when it trips). A response submit is
  limited to 30 a minute per client and form, checked before the request body is read.
  A refusal is a plain 429 in English or Dutch with `Retry-After`, the same whether or
  not the address has an account. The sign-in and form screens show it in the
  respondent's language. A request through a proxy that is not in `TRUSTED_PROXIES`
  has no client, so only the address and instance limits apply to it. The Submissions
  API keeps its own limits.
