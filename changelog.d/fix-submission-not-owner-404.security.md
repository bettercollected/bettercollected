- Someone else's submission is "not found" to a signed-in respondent: `GET` and `DELETE`
  `/workspaces/{id}/submissions/{submission_id}` answer 404, as for a submission that does not
  exist, to a caller who neither submitted it nor holds any permission in the workspace (it was
  403, which told them the id was real). Workspace members keep their answers.
