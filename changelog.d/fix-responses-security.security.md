- The deletion-request list no longer shows a response's receipt number to a member who
  cannot read responses (the Privacy officer). The number opens the answers without a
  sign-in, so handing it to a role that is meant to never read answers broke that
  separation of duties. Members who can read responses still see it.
- The backend's request log and APM traces no longer record query strings (the responses search sends a
  respondent's email there) or receipt numbers: it keeps the method, the path with the
  number replaced, and the status, and the server's own access log is off.
