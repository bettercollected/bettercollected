- Email sign-in codes are no longer stored as they are mailed. The auth service keeps a keyed
  hash of each code (HMAC-SHA256 with a key derived from `AUTH_AES_HEX_KEY`), bound to the
  account, whether the code was asked as a creator or a respondent, and its expiry, and compares
  it in constant time. Anyone who can read the auth database or a backup can no longer sign in
  with a pending code. Five wrong tries now clear a code (parallel tries count too), and a new
  one must be requested; an expired code is refused before it is compared, and a code signs in
  only once. Other changes to an account (names, plan, last sign-in) can no longer put back an
  older code or reset its count of wrong tries.
- Upgrading: codes sent before the upgrade are refused (they were stored in plain text; they
  expire within 5 minutes anyway), so anyone signing in at that moment asks for a new code. No
  data migration is needed. An account whose last code was sent before the upgrade keeps that
  expired plain-text value in the database until its next code is sent or checked. Rotating
  `AUTH_AES_HEX_KEY` likewise voids the codes pending at that moment.
- The auth service no longer returns an account's pending code to the backend (account lookups
  and the plan upgrade), its access log no longer records query strings (where the backend
  sends the email and the code), and its database errors no longer list a statement's
  parameters.
- Elastic APM no longer records what a request to the auth service carries. Every transaction,
  span and error it sends has no query string in a URL or name (the email and the sign-in
  code), no request headers (the internal key), cookies or body, no local variables of stack
  frames (which the auth service no longer collects at all) and no database parameters in an
  error message. The backend's APM guard now covers spans too: its calls to the auth service
  are recorded without their query strings. Both guards are built into the APM client, and no
  `ELASTIC_APM_*` setting switches them off.
