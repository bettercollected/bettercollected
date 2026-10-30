- The server now enforces a form's close date. Before, the date only hid the form from the
  public listing and the share menus: a direct link to a closed form still loaded it and
  accepted new responses. From the close instant on, a new response is refused with 409
  `form_closed` before anything is stored, uploaded or started. The time the backend
  received the request decides (behind a proxy that buffers uploads, the time the upload
  finished), for at most 10 minutes after it arrived. Respondents can still edit or ask
  to delete what they already sent. Forms whose close date has passed stop accepting
  responses when this version is deployed.
- A closed form's questions are no longer served on any respondent read: the published
  form, any of its versions, the public listing and the search. Respondents get the
  form's welcome page and look with a "closed" notice, without an AI notice token or a
  registration destination. A respondent whose form closes while they fill it in sees the
  same notice, and keeps their answers on the page. Workspace members still see the whole
  form, with a line saying respondents can no longer answer it.
- The close date is checked when it is saved: it is stored as a UTC instant (a value
  without an offset counts as UTC), an empty value removes it, and anything that is not a
  date is refused with 422. Values stored earlier, in any offset, are read as the same
  instant. The listing used to compare them as text, which was off by the offset.
