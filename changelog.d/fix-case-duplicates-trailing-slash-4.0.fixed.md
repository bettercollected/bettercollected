- Admin task `auth.resolve_case_duplicate_accounts` no longer refuses every run with
  `backend_unreachable`: the runner requested the API's routes with a trailing slash, which the
  API answers with a redirect the runner does not follow. It now requests their exact paths.
