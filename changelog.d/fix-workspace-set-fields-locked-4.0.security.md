- Workspace settings changed field by field (AI consent, single sign-on enforcement and default role,
  custom-domain status) are written atomically when the workspaces are served from Postgres
  (`DB_WRITE_MODE__identity=postgres_primary_dual` and beyond): two changes made at the same time
  both stay, so a concurrent save can no longer switch AI back on without consent or turn off
  required single sign-on. Upgrade before moving the identity group to Postgres.
