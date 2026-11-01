- `AUTH_JWT_SECRET` and `AUTH_AES_HEX_KEY` can now hold a key ring, `<current>[,<previous>]`: the
  first key signs and encrypts, every key verifies and decrypts (session tokens, stored secrets,
  OAuth and single sign-on state, sign-in codes, saved-draft links, list cursors and download
  links). A single key works exactly as before. This is what lets the keys be rotated without
  losing data or signing everyone out; the Temporal worker and the actions executor accept the
  same ring in `AES_HEX_KEY`.
