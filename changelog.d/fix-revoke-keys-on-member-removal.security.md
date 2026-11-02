- A workspace API key no longer outlives the person who made it. Removing a member left the keys they
  had created in place: they answered 403 while the person was away, but invited again (or provisioned
  again by the directory) the same person got every old key back under whatever role they then held.
  Removing a member, deleting an account and the directory deprovisioning a user now revoke the keys
  that person created in that workspace (in every workspace for an account deletion). The revocation
  is part of the member removal's own transaction, so a removal never leaves a live key, and each
  revoked key gets an `api_key_revoked` entry in the workspace's audit log first (key id, reason, the
  person; never a name, prefix or token). The key rows stay, revoked, so the audit and "last used"
  remain. Other members' keys are untouched, and keys revoked this way are not restored by inviting
  the person again.
