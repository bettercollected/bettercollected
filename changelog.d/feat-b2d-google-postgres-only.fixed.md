- The admin task runner no longer refuses its tasks with `write_mode_unknown` on a fresh stack that
  sets no `DB_WRITE_MODE`: an unset write mode is now the services' own default, as for the
  services themselves. A value that is not a write mode is still refused.
