- The responses list no longer shows "No responses yet" or "Nothing matches" while
  it is still waiting for the server, for example right after Retry or after
  clearing a search, and no longer swaps them for a loader when the same list is
  checked again. When the last rows of a later page are deleted, the list now goes
  back a page instead of saying the form has no responses. After Retry the
  keyboard focus stays in the list.
- Answers with several selected options now read "Reading, Cycling" in the
  responses table, on the response page and on the respondent's own view of their
  response, instead of "Reading,Cycling". The CSV export is unchanged.
- The deletion requests table no longer puts the full receipt number in a tooltip.
  It shows the first 8 characters, like the response page, also for numbers
  without dashes. A staff member who opens someone else's response on the
  submission page sees the number shortened too. The search box on the deletion
  requests tab is labelled for deletion requests.
- Signing out through "switch account" on an invitation, or when the session has
  ended, now also forgets the cached responses and the remembered responses list
  and search, like the logout button does.
