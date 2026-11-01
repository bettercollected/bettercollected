- `AUTH_JWT_SECRET` and `AUTH_AES_HEX_KEY` can now hold a key ring, `<current>[,<previous>]`: the
  first key signs and encrypts, every key verifies and decrypts (session tokens, stored secrets,
  OAuth and single sign-on state, sign-in codes, saved-draft links, list cursors and download
  links). A single key works exactly as before. This is what lets the keys be rotated without
  losing data or signing everyone out; the Temporal worker and the actions executor accept the
  same ring in `AES_HEX_KEY`.
- A secret the actions executor writes back (a refreshed Google Sheets credential) is opened
  with the backend's key ring and sealed again with its current key; a value no key of the ring
  opens is refused with a 422. The services now report in their heartbeat that they understand
  key rings.
- Upgrade note: the sign-in code hash and the PKCE verifiers of the Google Sheets and Google Forms
  OAuth flows are now derived from the encryption key as the one key parser reads it (surrounding
  spaces and one pair of quotes removed). A key stored with quotes or spaces gives different codes
  and verifiers than before: a sign-in code or an OAuth authorization started before the upgrade
  and finished after it fails once and is simply started again. A key without them is unchanged.
