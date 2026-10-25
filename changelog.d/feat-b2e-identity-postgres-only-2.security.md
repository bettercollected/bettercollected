- Workspace settings changed field by field (AI consent, single sign-on enforcement and default role,
  custom-domain status) are written atomically in Postgres: two changes made at the same time both
  stay, so a concurrent save can no longer switch AI back on without consent or turn off required
  single sign-on. Removing an invitation and disabling the other SSO connections of a workspace are
  atomic too.
