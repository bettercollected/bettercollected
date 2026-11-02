- Reusable sections, the library: a workspace keeps groups of questions saved once and copies them into
  forms. A copy gets new ids and its show/hide rules, choice logic, field rules, calculations, answer pipes
  and repeating groups point at the copy's own questions, and what pointed outside the group is left out
  when it is saved, with a note. A copy is never a live link, so a published form never changes by itself;
  a question remembers which section it came from, so a copy can be compared with the newest version and
  updated while the form's question ids stay for questions that stay the same. The edit operation
  `insert_library_section` lets the AI assistant, MCP and the API insert a section, and the builder's new
  `splice_fields` operation inserts and replaces complete questions. Library sections never leave their
  workspace. Needs the server setting `REUSABLE_SECTIONS_ENABLED` (off by default).
