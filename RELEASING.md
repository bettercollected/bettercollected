# Releasing

This document describes how maintainers cut a release of **bettercollected**.
It is intentionally simple and tag-based; we can automate it later.

## Versioning

We follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) at the
repository level, tagged as `vMAJOR.MINOR.PATCH` (e.g. `v2.2.0`):

- **MAJOR** — incompatible/breaking changes to APIs or data.
- **MINOR** — backwards-compatible features.
- **PATCH** — backwards-compatible bug fixes.

The tag is the source of truth for a release. Per-service `version` fields in
`package.json` / `pyproject.toml` are not the release version and don't need to
be bumped for every release.

## Conventional Commits

Commits and PR titles should follow
[Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add matrix field to the form builder
fix(auth): reject expired OTPs
docs: correct local setup steps
chore(deps): bump next to 16.2
```

Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`,
`perf`, `build`. A `!` after the type (or a `BREAKING CHANGE:` footer) marks a
breaking change. Consistent prefixes make the changelog easy to assemble and let
us automate release notes later.

## Cutting a release

1. **Pick the version.** Review merged PRs since the last tag and decide
   major/minor/patch from the nature of the changes.
2. **Update the changelog.** In [CHANGELOG.md](CHANGELOG.md), move the relevant
   entries from `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section,
   and update the compare links at the bottom. Keep an empty `Unreleased`
   scaffold for the next cycle.
3. **Merge** that changelog PR to `develop`.
4. **Tag** the release commit and push the tag:

   ```bash
   git checkout develop && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

5. **Publish GitHub release notes.** Create a release from the tag; use the
   changelog section as the body. GitHub's "Generate release notes" can seed it
   from the Conventional-Commit history.
6. **Verify deploys.** Confirm the deployment workflow(s) picked up the release
   as expected.

## Keeping the changelog current

Prefer to note user-facing changes under `## [Unreleased]` **as part of the PR
that makes them**, rather than reconstructing everything at release time. Small,
continuous updates keep the release step to a few minutes.

## Future automation

Candidates when the cadence justifies it: `release-please` or
`semantic-release` to derive versions and changelog entries from Conventional
Commits automatically. Not adopted yet to keep the monorepo release process
transparent and low-magic.
