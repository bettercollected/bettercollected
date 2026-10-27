- A form can be downloaded as an Open Formulieren import archive, behind the new switch
  `OPEN_FORMULIEREN_EXPORT` (`off` by default; `on` enables
  `GET /workspaces/{id}/forms/{form_id}/open-formulieren-export` for members who may read the form and
  adds `exportMode` to the providers entry). The archive holds the form's structure only: pages, questions,
  choices, answer rules, simple show/hide rules and the retention days. Responses, staff-only questions,
  secrets and scripts are never in it; what has no equivalent (calculated fields, page jumps, ratings and
  more) is left out and listed in a `README.txt` inside the archive, with the count in the
  `X-Open-Formulieren-Unmapped` header. See `docs/open-formulieren.md`.
