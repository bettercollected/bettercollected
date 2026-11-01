- Key rotation: `reencrypt` now exits with a failure and lists the response ids when a signature
  image written again for a response that had lost its signature could not be removed, so an
  erased signature left in storage is no longer reported as a clean run.
