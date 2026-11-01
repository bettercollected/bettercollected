- Rotating the response encryption keyset now covers drawn signature images: `reencrypt`
  seals each image still under an old key again under the new one, and `drop-old` refuses
  to remove a key while any image is sealed under it or cannot be checked. The
  `keyset.drop_old` admin task cannot reach the file store, so it refuses while a drawn
  signature exists and an old key is still to drop. On a stack whose keyset lives only in
  the settings store (no `MASTER_ENCRYPTION_KEYSET` in the services' environment, so the
  script cannot be used), the old keys therefore stay while any drawn signature exists:
  nothing is lost, and keeping a key is safe.
