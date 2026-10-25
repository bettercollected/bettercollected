- Single sign-on switched on (`SSO_ENABLED=true`) but not fully set up no longer claims to be off: the workspace
  SSO page now says it is switched on but not fully set up yet (English and Dutch; the overview API answers
  `reason: "not_configured"`, and `reason: "disabled"` when it is off), the backend and auth log the missing
  settings by name at startup, and the admin portal's Health page lists them per service. Names only, never values.
