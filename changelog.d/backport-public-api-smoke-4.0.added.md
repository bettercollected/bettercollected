- Staff with `privacy.manage` close a pending deletion request by hand, without the form's provider:
  `POST /workspaces/{id}/forms/{form_id}/submissions/{response_id}/deletion-request/close` with
  `outcome` `completed` (the workspace's stored copy is deleted) or `declined` plus a reason from a fixed list.
  Responses imported from Google Forms could only be cleared by deleting them at the source and syncing again.
  Who closed a request and when is kept on it (every close is appended, never overwritten), and a later sync no
  longer brings back a response whose deletion request was completed. `completed` is refused (409) while a copy
  of the response that the workspace may own cannot be attributed to it. Respondents see a declined request as
  "Not deleted: <reason>" (English and Dutch), never as deleted.
- Public API: `DELETE /forms/{formId}` deletes a form and its responses. It needs the new key
  scope `forms:delete` ("Delete forms" when creating a key; `forms:write` does not allow it, so no
  existing key gains it) and a key creator with `form.delete`.
  `POST /forms/{formId}/responses/{responseId}/deletion-request/close` closes a pending deletion
  request as `completed` or `declined` with a fixed reason (`deletion_requests:write`; the creator
  needs `privacy.manage`).
