- Re-sending a pending invitation from a member's menu asks for the mail in the browser's
  language (Dutch or English), like the resend on the invitations list; `POST
  /workspaces/{id}/members/invitations/{token}/resend` takes the same optional `locale` as a new
  invitation.
