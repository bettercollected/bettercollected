- Two edits of one response made at the same time, two filings of the same deletion request, two
  staff members closing one request, and two saves of one responder group, one tag title or one
  responder now apply one after the other instead of overwriting each other: a repeated filing is
  refused as "already exists", and a request closed by someone else meanwhile answers 409.
  Completing a deletion request while another staff member declines it deletes nothing and
  answers 409. A wait for a record another write is holding, past the lock timeout, answers 409
  `busy` instead of a server error.
