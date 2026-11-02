- Staff edit of answers (still off by default, `RESPONSE_REVISIONS_ENABLED`): a deletion request filed while an edit is
  made is now checked under the response's lock, a save made on an out-of-date history is refused with a "changed
  meanwhile, reload" message (`expectedSeq`), only the question types the dialog offers can be written, a staff edit
  and every read of previous values are recorded in the workspace audit log (ids only, never a value), and an entry
  that cannot be opened for option-source redaction is counted in a log warning.
