- Forms can create an object in an Objects API for each submission (behind `OPEN_FORMULIEREN_REGISTRATION`, off
  by default). A service is an Objects API address, an object types address that fences each form's object type
  URL, and a read-and-write token; a form maps answers to paths in the object and gets a "check connection".
  A retry looks for the object it may already have created, and never counts a lookup hit as delivered unless
  the object carries the delivery's reference.
  Registration service addresses (Generic JSON too) with a `..` or `.` path segment, or an
  encoded slash or backslash, are now refused (`invalid_url`).
