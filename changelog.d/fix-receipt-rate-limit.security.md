- The public receipt routes (reading a response by its receipt number, and requesting its
  deletion) are now rate limited, so receipt numbers can no longer be tried at full speed.
  Per client address and 10-minute window: 60 requests per route and 10 unknown numbers
  (both routes together; after that every lookup answers 429 with `Retry-After` until the
  window ends), plus 1000 unknown numbers for all clients together. The counters are
  shared by every backend replica and hold neither the number nor the address. Set them
  with `API_RECEIPT_REQUESTS_PER_WINDOW`, `API_RECEIPT_MISSES_PER_WINDOW`,
  `API_RECEIPT_GLOBAL_MISSES_PER_WINDOW` and `API_RECEIPT_WINDOW_SECONDS` (0 turns a
  limit off). Behind a reverse proxy, set `TRUSTED_PROXIES`, or every visitor shares the
  proxy's limit.
