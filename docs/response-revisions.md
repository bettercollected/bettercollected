# Staff edit of answers and the history of a response

Behind the server setting `RESPONSE_REVISIONS_ENABLED` (default off; see `docs/settings-inventory.md`). While it is off
a staff edit and the history are refused (422 `response_revisions_disabled`), the response page shows neither, and
**nothing is recorded**, not even when a respondent edits their own answers: the product behaves as before.

## Who may change answers

The permission `response.edit` ([enterprise-access-model.md](enterprise-access-model.md)): Owner, Admin and Editor. A
Reviewer, a Viewer and a Privacy officer cannot (the Privacy officer never holds a permission that touches answers), and
neither can an API key or the MCP server. Whoever edits must also hold `response.read`.

## What an edit is checked against

The same checks as a respondent's own edit (one function serves both): the form's rules, required questions, types and
patterns, date rules, calculated values and the values a rule sets or locks (the server's values win), and repeating
groups. Differences, on purpose:

- the form **version the response was given in** is the reference (the version the response page shows), not the latest;
- **a signature or a file cannot be changed** (a signature is the respondent's own mark and carries a server stamp);
- **a response with a pending deletion request cannot be edited**, nor a response imported from another service;
- internal fields keep their own route (`response.annotate`); the other questions are edited here.

An edit that changes nothing writes nothing. Staff editing has no time window. The respondent is **not notified**, and
no webhook, email action or other action runs again for an edited response (a respondent's own edit does not either);
exports and the API show the current answers.

## The history

Every edit by staff **and** by the respondent adds one entry: who (staff with their role, or "respondent"), when, which
questions changed, and the values they had before. The previous values are sealed with the response keyset, like the
answers; the list shows who, when and which questions, and one entry's values are opened on request. Both need
`response.read` (the response's own readers); nothing else reads them. The history is stored in `response_revisions`
(revision 0032) in the transaction of the edit, so a change and its entry succeed or fail together, and it is deleted by
the database together with the response (a deletion by a person, a deletion request, a form, a workspace, retention).
A staff member's account deletion replaces their id with `deleted-user`. A response keeps at most 200 entries; after
that it cannot be edited again (the history is never trimmed).

A signature or file image a respondent replaces is deleted as before, so the history keeps the answer's record (the
file's name, "signed") but not the image.

## Not covered yet

Rotating the response keyset (`docs/response-keyset-rotation.md`) does not re-seal `response_revisions` yet. Do not drop
the old key from the keyset while entries exist.
