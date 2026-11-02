- Editing an API key's role or list of forms no longer holds up the requests made with that key.
  The edit is now worked out before the key's row is locked, and the lock covers only a check
  that the key is unchanged, its audit entries and the write (an edit that finds the key changed
  meanwhile is worked out again, and answers 409 `key_changed` if that keeps happening). The
  last-used update that every request with a key makes now skips a key that is being edited or
  revoked instead of waiting for it, so under load those requests no longer wait for the
  database's lock timeout and fail.
