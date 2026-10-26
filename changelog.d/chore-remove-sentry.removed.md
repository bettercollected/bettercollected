- The Sentry error reporter is gone from the backend and auth services (and its unused setting
  from the Google Forms service): no error report leaves for a third party any more.
  `SENTRY_DSN` and `SENTRY_DEBUG` can be dropped from deployments; leaving them set is harmless
  (they are ignored, as are stored rows for them).
