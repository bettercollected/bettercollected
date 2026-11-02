- The workspace audit log now records who invited, removed or changed the role of a member, who
  revoked an invitation (and when one was accepted), who published or deleted a form, who deleted a
  response, and each export, bulk read or response PDF (a pointer to the export's own record).
  Entries hold ids and enum values only: no names, addresses or answers. Inviting, revoking,
  removing, changing a role and deleting a form or a response are written before the change and
  refused (503 `audit_unavailable`) when the entry cannot be stored; the others are best effort.
  Nothing reads these entries in the product yet.
