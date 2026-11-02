- Directory groups can feed a team (behind `FORM_ACCESS_ENABLED`, off by default; with the switch
  off the two new routes answer 422 `form_access_off`): the owner links a directory (SCIM) group
  to a team under Workspace, Members, Teams, "Linked directory groups", or with
  `PUT/DELETE /workspaces/{id}/scim/groups/{group_id}/team`. One group is in one team, a team may
  take several groups, and no one below the owner can change a link. The people in a linked group
  are in the team while the directory says so, read when a request is decided and never copied:
  deactivating or deleting someone in the directory, or taking them out of the group, ends the
  access their team gave them on the next request, with no sync step in between. A person in
  a team through a group is removed in the directory, not on the team page. Linking and
  unlinking are written to the audit log (ids only), also when the directory deletes a linked
  group.
  Adds migration 0039 (a table for the links and an index on directory users' accounts).
