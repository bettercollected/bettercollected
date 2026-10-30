- A form's close date is now enforced by the server. Before, it only hid the form from the
  public listing and the share menus: a direct link to a closed form still loaded it and
  accepted new responses. From the close instant on, a submission is refused with 409
  `form_closed` before anything is stored, uploaded or started, judged by the time the
  request arrived; respondents get the form's welcome page with a "closed" notice instead
  of its questions, and the public listing and search leave it out. Respondents can still
  edit or ask to delete what they already sent. Forms with a close date in the past stop
  accepting responses when this version is deployed.
- The close date is checked when it is saved: it is stored as a UTC instant (a value
  without an offset counts as UTC), an empty value removes it, and anything that is not a
  date is refused with 422. Values stored before, in any offset, are read as the same
  instant; the listing no longer compared them as text, which was off by the offset.
