- Versions page for a form (behind `FORM_REVISIONS_UI_ENABLED`, off by default): staff list the published versions
  with who published each and when, read one read-only, compare two in plain language (English and Dutch) and
  restore one into the draft. Restoring never changes or deletes a version; publishing the draft makes a new one.
  A response page names the version the response was given in and links to it.
  A restore holds the old version to the checks of a save (first-party images, http(s) links), so a version
  published before a check existed cannot bring a refused value back.
