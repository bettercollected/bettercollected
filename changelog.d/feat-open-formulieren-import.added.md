- Forms exported from Open Formulieren can be imported as drafts, behind the new switch
  `OPEN_FORMULIEREN_IMPORT` (`off` by default; `on` offers it in the providers list and enables
  `POST /workspaces/{id}/open-formulieren-imports`). The import reads the 4.0 series' export archive
  with hard limits (it is untrusted: nothing in it is run, rendered or fetched), builds the draft through
  the form edit operations, never publishes it, marks it "needs review" and reports everything that was
  dropped, converted or flagged (sign-in, prefill, payment, appointments, custom scripts, translations
  and variables are not carried; a national identity number question is flagged). See
  `docs/open-formulieren.md`.
