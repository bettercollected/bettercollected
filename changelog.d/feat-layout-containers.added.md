- Layout containers: a form creator can group the questions of a page into a panel (a titled group
  that opens and closes, open or closed when the page opens), a field set (a bordered group with a
  legend) or tabs (one group of questions shown at a time). It is layout only: answers, logic,
  field rules, calculations, piping and the exports see the questions as before, and a container
  can be shown or hidden by an earlier answer (the questions in a hidden container are not
  required, and what they hold stays stored). The form spec has a `containers` key on a page
  (documented in `docs/spec/README.md`), the operation `set_page_containers` edits them, and the
  MCP server and the AI assistant know it. It is behind `LAYOUT_CONTAINERS_ENABLED`, which is off
  by default; containers a form already has keep working either way.
