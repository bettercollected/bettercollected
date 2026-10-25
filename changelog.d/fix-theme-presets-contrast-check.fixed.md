- Saving a workspace theme through the API now runs the same contrast check as publishing:
  a theme whose colours fail WCAG 2.2 AA is refused with a 422 (`theme_contrast`) naming
  each failing pairing and the nearest colours that pass, so a saved theme can no longer
  make every form that uses it fail at publish. Themes already saved are kept as they are.
