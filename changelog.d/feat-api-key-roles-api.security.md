- Revoking an API key, and every automatic revocation (a member removed, an account deleted, a
  directory deprovisioning), now also deletes the key's list of forms, in the same transaction. When a
  workspace is deleted, every API key of it is revoked, including those of its other members.
