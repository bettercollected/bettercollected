- Copying a form to another workspace: the target's access mode is now checked inside the transaction of the
  write itself (under a share lock on its link), so a restricted form can never land in a target that was
  opened meanwhile; a copy that failed because the audit log was down (503) can be sent again with the same
  Idempotency-Key instead of replaying the failure; saving a form's link no longer loses a concurrent
  copied-from mark; the dialog asks for the other workspaces' permissions a few at a time, however many
  workspaces there are, and makes its Idempotency-Key only from the browser's secure random source.
