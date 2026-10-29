- Publishing: the colour-contrast check now holds new forms, forms that were never published
  and any colour change to WCAG 2.2 AA. A form made before the check that is already live
  keeps publishing with the colours it went live with: the builder lists its hard-to-read
  colours as a recommendation ("Publish anyway" stays available) instead of blocking, in
  English and Dutch. Once its colours differ from the live version's, they have to pass like
  any other form's. Forms are now created under publish-checks version 3; the "why we ask
  this" and workspace-title rules keep the versions they had.
- Colour contrast: an outlined button is measured by its real text and edge colours (its ink
  on the page, 4.5:1 for the text and 3:1 for the edge) instead of as white text on the button
  colour, in the builder and on the server (shared cases in
  `docs/spec/theme-contrast.cases.json`). A mid-tone button colour that reads fine as an
  outlined button is no longer refused, and the suggested colours move it only as far as the
  chosen-answer colour needs.
