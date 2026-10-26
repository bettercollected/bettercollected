- The identity that ties an anonymous response to its respondent is now a keyed hash
  (`v2:` + HMAC-SHA256 under a new `RESPONDENT_IDENTITY_KEY`) instead of an unsalted MD5 of the email
  address, so knowing an address no longer lets anyone link its "anonymous" responses. Stored values
  convert in one idempotent, resumable pass that needs no address (run at every API start, or by hand
  with `python -m backend.identity_rekey`); matching refuses any value that is not `v2:`.
