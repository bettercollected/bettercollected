- A failing rate limiter (a database error or a lock timeout on its counters) no longer
  turns a sign-in code request or a form submit into a 500: the request is let through and
  the error class is logged. A real 429 is still a 429. Expired rate-limit counters are
  now deleted in the background (bounded batches, at most once a minute per process)
  instead of on every new counter (almost every submit).
