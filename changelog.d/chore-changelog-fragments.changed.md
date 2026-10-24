- Changelog entries are now files in `changelog.d/` (`<pr-number-or-branch-slug>.<category>.md`)
  instead of edits to `CHANGELOG.md`, which a release assembles them into with
  `.github/scripts/changelog.py assemble X.Y.Z` (`--draft` previews). A PR check fails when a pull
  request changes code without a fragment (unless it is labelled `no-changelog`) or edits
  `CHANGELOG.md` outside a `docs/changelog-X.Y.Z` release branch. See `changelog.d/README.md`.
