- The responses list can now be filtered, sorted and paged on the server. Filter
  by the day a response was submitted (a range in the viewer's own time zone), by
  the state of its deletion request, by anonymous or identified responders and by
  form version, combined with the responder-email search; sort by newest, oldest
  or form version; pick 25, 50 or 100 rows. A pager with first, previous, nearby,
  next and last pages (real links, reachable by keyboard) replaces the numbered
  strip, a polite count says which rows are shown (a total above 10,000 reads
  "10,000+", and then there is no last page), and the page scrolls as a whole
  instead of inside a 65vh box. Filters, sort, size and page are in the address,
  so a list can be shared and survives Back and Forward; the responder search
  stays out of it on purpose. Dutch and English. Answers stay encrypted, so
  there are no answer-level filters.
- The list endpoint (`GET .../forms/{form_id}/submissions`) takes `paging=keyset`,
  `submittedFrom`, `submittedTo` (UTC instants), `status`, `respondent`,
  `formVersion` and `cursor`. It pages by keyset on the submitted time, so the
  next, previous and nearby pages cost the same at any depth (a signed,
  expiring cursor names where a page began; a tampered one or one from another
  list is refused with 400 `invalid_cursor`). Without these parameters it
  answers as before. Migration 0024 adds an index for the form-version sort and
  one on the deletion requests' `response_id`; the build blocks writes to those
  tables for a moment (the statements are in the migration for a manual,
  concurrent build first).
