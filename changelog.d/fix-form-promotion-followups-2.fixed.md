- Copying a form to another workspace: a copy whose write changed nothing (the draft already was that document)
  no longer marks the form as copied, the workspace picker stops asking once the dialog is closed and says it
  failed when every request failed instead of "no other workspace", and a check handed to the form write
  without the conditional write it runs in is refused instead of skipped.
