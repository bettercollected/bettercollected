- Forms can show respondents a review page before they send their answers. The
  new "Review answers before sending" switch in the builder's Form tab (off by
  default; also `showReviewPage` in the form spec, the API, the edit operations
  and the SDKs) adds a page after the last question that lists the answers of
  the pages the respondent went through, with an "Edit" button per page and
  "Back to review" on the page they return to. Answers to questions the form no
  longer shows, and uploaded files of those, are still sent as before; the
  page names them, and the values the link carried, in an "Also sent"
  block. Nothing is sent or stored until the
  respondent submits from it.
