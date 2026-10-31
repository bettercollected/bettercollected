- Forms can show respondents a review page before they send their answers. The
  new "Review answers before sending" switch in the form's settings (off by
  default; also `showReviewPage` in the form spec, the API, the edit operations
  and the SDKs) adds a page after the last question that lists the answers of
  the pages the respondent went through, with an "Edit" button per page and
  "Back to review" on the page they return to. Nothing is sent or stored until
  they submit from it.
