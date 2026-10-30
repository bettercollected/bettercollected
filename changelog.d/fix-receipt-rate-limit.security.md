- The public receipt routes (reading a response by its receipt number, and requesting its
  deletion) are now rate limited, so receipt numbers can no longer be tried at full speed.
  Per client address and 10-minute window: 60 requests per route and 10 unknown numbers
  (both routes together; after that every lookup answers 429 with `Retry-After` until the
  window ends). The counters are shared by every backend replica and hold neither the
  number nor the address. Set them with `API_RECEIPT_REQUESTS_PER_WINDOW`,
  `API_RECEIPT_MISSES_PER_WINDOW` and `API_RECEIPT_WINDOW_SECONDS` (0 turns a limit off).
  `API_RECEIPT_GLOBAL_MISSES_PER_WINDOW` is an emergency switch, off (0) by default: a cap
  on all clients' unknown numbers together, after which receipts answer 429 for everyone
  until the window ends. The receipt pages say "Too many attempts. Try again in a few
  minutes." instead of "not found" when a lookup is refused.
- Upgrading: the limits count per client address, so check that `TRUSTED_PROXIES` covers
  your reverse proxy's current address. Prefer the CIDR of the network between the proxy
  and the backend over a single container address, which changes when the container is
  recreated (host names are not accepted). The backend now also logs a warning, once per
  process, when a proxy at a private address sends `X-Forwarded-For` but is not in
  `TRUSTED_PROXIES`. The receipt limits are live settings: if receipts start answering
  429 for everyone, set them to 0 in the admin portal.
