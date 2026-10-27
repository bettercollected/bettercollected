- Workspace admins can add an Objects API as a place to send submissions, next to Generic JSON: its address,
  the object types address and a write-only token. On a form, the settings take the object type address
  (checked against the service's object types address), its version, a reference path and, per answer, the
  place it goes in the object's data (`a.b.c`); file questions are shown as not supported. A "Check
  connection" button asks the Objects API whether the saved settings work, without reading or creating a
  record. The results page names every reason a submission was not sent, in plain words with what to do
  next, and shows the id of the created object. The respondent's privacy panel now also says that deleting
  answers there does not delete the copy at the organisation, and that they should contact it for that.
