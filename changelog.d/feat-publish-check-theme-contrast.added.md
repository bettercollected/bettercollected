- Publishing: a `theme_contrast` publish check holds the form theme's own colours to
  WCAG 2.2 AA contrast (text 4.5:1, controls 3:1) on every publish path, so forms
  published through the public API, the MCP server or after an AI assistant edit are
  guarded like the builder. The refusal names each failing colour pair with its ratio
  and the nearest colours that pass; text over an image background is advisory only.
  The rules are shared with the builder through `docs/spec/theme-contrast.cases.json`.
