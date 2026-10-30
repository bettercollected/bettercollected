- The deletion-request list no longer shows a response's receipt number to a member who
  cannot read responses (the Privacy officer). The number opens the answers without a
  sign-in, so handing it to a role that is meant to never read answers broke that
  separation of duties. Members who can read responses still see it.
- The backend's request log no longer records query strings (the responses search sends a
  respondent's email there) or receipt numbers: it keeps the method, the path with the
  number replaced, and the status, and the server's own access log is off.
- Responses that carry decrypted answers (the submission lists, one submission, the
  export, the submission paths and the receipt by number) are now sent with
  `Cache-Control: no-store` and `Pragma: no-cache`, so a browser on a shared computer
  does not keep them or show them again on back/forward.
- The receipt opened by its submission number (no sign-in) still shows the answers but no
  longer returns the respondent's email or their anonymous identity, only whether the
  response was anonymous.
