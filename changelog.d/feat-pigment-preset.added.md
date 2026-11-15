- **Pigment theme preset** (off until `APP_THEME_PIGMENT_ENABLED` is turned on, the
  switch of the second app theme): iris on warm cream paper, a sun-yellow band over the
  questions, lettered answer keys in five flat colours (the letter, not the colour, names
  an option), the chosen option solid iris with a check, and, when the form is sent, five
  flat shapes that pop in around the check once (CSS only; with reduced motion they are
  simply there). It sets colours only: fonts, corners and buttons stay the form's own.
  Creators pick it in the Design tab; it is not the default for new forms. With the switch
  off the picker, the edit operations, the AI and the MCP server do not know it, a new
  theme cannot name its artwork (form saves, saved themes and operations refuse it), and
  forms that already wear it render and save as before. Turning on
  `APP_THEME_PIGMENT_ENABLED` also offers this preset, its artwork and the lettered choice
  keys (the same switch covers the workspace appearance choice and these). The text on the
  yellow band keeps 4.5:1 for any theme, and the contrast check reports it.
