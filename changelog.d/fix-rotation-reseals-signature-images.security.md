- Rotating the response encryption keyset now covers drawn signature images: `reencrypt`
  seals each image still under an old key again under the new one, and `drop-old` refuses
  to remove a key while any image is sealed under it or cannot be checked. The
  `keyset.drop_old` admin task, which cannot reach the file store, refuses while a drawn
  signature exists and an old key is still to drop; use the script for such a stack.
