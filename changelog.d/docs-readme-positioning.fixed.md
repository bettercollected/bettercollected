- `backend/.env.example` works as a starting point again: a copy no longer fails to load because of
  empty values that are not valid (`API_ENABLE_EXPORT_CSV`, `AWS_PRE_SIGNED_URL_EXPIRY`,
  `DEFAULT_WORKSPACE_ID`) or inline comments read as values (`VERIFIED_DOMAINS_NAMESERVERS`).
