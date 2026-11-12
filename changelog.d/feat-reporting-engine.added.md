- Reports on a form's answers, server side: counts, averages, distributions and over-time
  series computed on request (`POST .../forms/{form_id}/report/query`, and the catalogue of
  what can be reported at `GET .../report/fields`). For people who may read a form's
  responses and its analytics; never text, identities or a typed "Other" answer. Answers
  stay encrypted at rest and are added up in memory. Off until `REPORTING_ENABLED` is set
  (environment only, default off); see `docs/reporting.md`.
