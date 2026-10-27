- Registration of submissions in a case system, behind `OPEN_FORMULIEREN_REGISTRATION` (off by default): workspace
  admins add services (https address, encrypted write-only secret) and choose per form which variables are sent as a
  Generic JSON body (the format Open Formulieren sends). Delivery runs as a background job with retries, a visible
  failure and a retry button; the respondent's privacy panel names the destination. Not yet tested against a live
  environment. See `docs/open-formulieren-registration.md`.
