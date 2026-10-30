- The CSV export of responses now has the response id, the submission time (UTC, ISO 8601)
  and one column per hidden field at the end of each row, so existing columns keep their
  place (a form without repeating groups gains a Response ID column). Responders without an
  email show as "Anonymous" instead of "- -", and multi-select answers, staff fields
  included, are joined with "; ". Text a spreadsheet could run as a formula still gets a
  leading apostrophe: only plain negative decimals such as -12.5 are left as they are,
  and phone numbers starting with "+" keep a visible apostrophe, because a spreadsheet
  would otherwise evaluate them (+31-6-1234-5678 is a subtraction). Leading spaces and
  line breaks before = + - @ are guarded too.
