- A form can open on a date and stop after a number of responses. Before its open
  date, and once it holds as many responses as its limit, the server refuses new
  responses (409 `form_not_open` / `form_full`), as it does for a closed form, and
  respondents see a notice in their own time zone and language instead of the
  questions. The limit is counted under a lock, so responses sent at the same
  moment never pass it; deleting a response frees its place. Editing a response
  and asking for its deletion are not affected. Both settings are in the form's
  settings, and forms that are not open yet or full leave the public listing and
  the search like closed ones.
