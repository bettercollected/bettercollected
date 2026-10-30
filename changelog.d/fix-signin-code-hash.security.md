- Email sign-in codes are no longer stored as they are mailed. The auth service keeps a keyed
  hash of each code (HMAC-SHA256 with a key derived from `AUTH_AES_HEX_KEY`), bound to the
  account's email, whether the code was asked as a creator or a respondent, and its expiry, and
  compares it in constant time. Anyone who can read the auth database or a backup can no longer
  sign in with a pending code. Five wrong tries now clear a code (parallel tries count too), and
  a new one must be requested; an expired code is refused before it is compared, and a code
  signs in only once.
- Upgrading: codes sent before the upgrade are refused (they were stored in plain text; they
  expire within 5 minutes anyway), so anyone signing in at that moment asks for a new code. No
  data migration is needed. Rotating `AUTH_AES_HEX_KEY` likewise voids the codes pending at that
  moment.
- The auth service's account lookups for the backend no longer include an account's pending
  code, and its access log no longer records query strings, where the backend sends the email
  and the code being checked.
- Elastic APM on the auth service now records a request's method and path only: no query
  string (the email and sign-in code), no request headers (the internal key), cookies or body,
  and no local variables of an error's stack frames. Like the backend's guard, it is built into
  the APM client, and no `ELASTIC_APM_*` setting can switch it off.
