- The command line tool (`bettercollected`, Python SDK) has two new commands.
  `create` makes a new draft form from a file. `promote` copies a form from one workspace
  or instance to another as a draft, for example staging to production: it shows what is
  adjusted and what never moves (responses, webhooks and other automations, sharing, the
  form's link, publish state, the logo file) and a diff against the target form, supports
  `--dry-run`, and never publishes. An existing target form keeps its own retention,
  purpose and privacy link unless `--copy-privacy` is given. API keys are read from the
  environment or a private config file, never from the command line, and are never
  printed. The new page `docs/environments.md` explains it.
