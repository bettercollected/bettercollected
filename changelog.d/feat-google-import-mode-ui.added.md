- The dashboard follows the Google Forms import switch (`importMode` from `GET /providers`).
  In `readonly` the New form page no longer offers "Import Google Form" and says why, and the
  import dialog and the forms list (when it shows imported Google forms) explain that forms and
  responses imported earlier stay while new imports and re-syncs are no longer possible. In
  `off` Google Forms is not offered; the forms list says imported forms stay, and the Google
  Sheets action explains that it cannot be connected. A 403 `google_forms_readonly` or 410
  `google_forms_off` from the backend shows the same explanation (English and Dutch).
