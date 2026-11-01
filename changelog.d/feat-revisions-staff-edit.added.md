- Staff edit of answers with a history (behind `RESPONSE_REVISIONS_ENABLED`, off by default): a new permission,
  `response.edit` (Owner, Admin and Editor), lets staff change a response's answers, checked like a respondent's own
  edit (not for signatures or files, nor with a deletion request pending). Every edit, by staff or by the respondent,
  is kept in the response's history: who, when, which questions, and the previous values sealed with the response
  keyset. The history is deleted with the response. Adds a database table (revision 0032).
