- A failing rate limiter (a database error or a lock timeout on its counters) no longer
  turns a form submit into a 500: the submit is let through and the error class is
  logged. The sign-in code routes fail closed instead: on a limiter error they answer 503
  with `Retry-After: 60` and send no mail, so the instance breaker is never skipped. A real
  429 is still a 429. Expired rate-limit counters are now deleted in bounded batches, at
  most once a minute per process, instead of on every new counter (almost every submit).
