- **A `choiceKeys` theme key** (`letters`): a form theme can ask for lettered keys
  (A, B, C, ...) on the answer options of choice questions, small squares with an ink
  letter on a flat pigment, with the chosen option filled in the action colour and
  ending in a check. The letters work as the keys of the other themes with corners
  do (press a letter on an option to choose it); the key is decorative and the option
  is still named by its label. Optional: the Pigment preset sets it and no other preset
  does, and every existing form looks as before. Accepted by the edit operations, the
  form spec, whole-form saves and saved themes, while the Pigment switch
  (`APP_THEME_PIGMENT_ENABLED`) is on: while it is off a new theme that sets the key is
  refused (422 `theme_not_allowed`, or the operation's error) wherever it comes from,
  and a form or saved theme that already has it keeps saving. With the Leaflet style
  (ruled rows, no boxes) the keys are shown but the chosen row is not filled solid: it
  is marked by its bold label and the check. An outlined button style does not change
  the chosen row: the button colour must still hold white text at 4.5:1, which the
  contrast check now measures for a theme with the key.
