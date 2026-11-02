- With `FORM_ACCESS_ENABLED` off, the backend now logs one warning at startup when restricted
  forms, form grants or teams are stored: those forms are open to every member's workspace role
  while the switch is off, as before, and the operator is now told how many (counts only, no
  names or ids). The check is one read bounded by a two-second statement timeout; with the
  switch on it runs no query, and a failure of the check never stops the start.
