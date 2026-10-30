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
2. **Assemble the changelog.** On a branch named `docs/changelog-X.Y.Z` (the only
   branches the PR check lets edit CHANGELOG.md):

   ```bash
   python3 -I .github/scripts/changelog.py assemble --draft   # preview, changes nothing
   python3 -I .github/scripts/changelog.py assemble X.Y.Z     # --date YYYY-MM-DD, --previous A.B.C
   ```

   `assemble` moves everything under `## [Unreleased]` (entries already there are
   kept) and every fragment in [changelog.d/](changelog.d/README.md) into a new
   `## [X.Y.Z] - YYYY-MM-DD` section, categories in the order CHANGELOG.md uses and
   fragments sorted by name (PR numbers first, numerically). It leaves an empty
   `## [Unreleased]`, adds the compare link (from the newest version in the file;
   `--previous` when the last release was cut from another branch) and deletes the
   fragments. Review the section, add a summary paragraph under the heading if the
   release needs one, and commit.
3. **Merge** that changelog PR to `develop` (or to the `release/X.Y` branch for a
   patch release cut from it).
4. **Tag** the release commit and push the tag:

   ```bash
   git checkout develop && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

5. **Publish GitHub release notes (optional).** Pushing the tag is what ships a release;
   a GitHub release is only needed for a large set of changes or when someone asks for
   one. If you create it, use the changelog section as the body.
6. **Verify deploys.** The deployment workflow deploys `develop` and `master` to the
   development and staging stacks; production is deployed only from `vMAJOR.MINOR.PATCH`
   tags (optionally with a pre-release suffix), and any other tag name is refused. Confirm
   it picked up the release as expected.

## Keeping the changelog current

Every PR notes its user- or operator-facing changes **as part of the PR that makes
them**, as a fragment file in [changelog.d/](changelog.d/README.md)
(`<pr-number-or-branch-slug>.<category>.md`) rather than an edit to CHANGELOG.md, so
pull requests do not conflict on the changelog. The `Changelog fragment` PR check
requires one when a PR changes code (label `no-changelog` when nothing notable
changed) and refuses direct CHANGELOG.md edits outside `docs/changelog-*` branches.

## Merging a release branch forward

Fixes released from a `release/X.Y` branch reach `develop` through one merge, not per-PR
ports. Merge-forwards use a branch named `merge/release-<x>-into-develop` (e.g.
`merge/release-4.0-into-develop`), made from `develop`, into which `release/X.Y` is merged.
In CHANGELOG.md, the release branch's dated sections go under develop's `## [Unreleased]`,
and the entries and fragments on develop that those releases already list are removed. The
`Changelog fragment` check treats such a branch as a branch sync, like `release/*`.

## SDK releases

The SDKs in [sdk/](sdk/) are versioned and released on their own, separately from
the app, each with its own semver starting at `0.1.0`:

| SDK | Package | Version in | Tag |
|---|---|---|---|
| Python | [`bettercollected`](https://pypi.org/project/bettercollected/) on PyPI | `sdk/python/pyproject.toml` | `sdk-py-vX.Y.Z` |
| TypeScript | [`@bettercollected/sdk`](https://www.npmjs.com/package/@bettercollected/sdk) on npm | `sdk/typescript/package.json` | `sdk-ts-vX.Y.Z` |

The tags never match the app's `vX.Y.Z` pattern, so they do not start the app's
Build and Deploy (or any other workflow but the SDK one). Each README states the
oldest bettercollected version whose API the SDK works with; raise it there when an
SDK starts using a newer API.

1. **Bump the version** in a pull request: `version` in `sdk/python/pyproject.toml`
   (then `uvx uv@0.12.23 lock` in `sdk/python`), or `version` in
   `sdk/typescript/package.json` (then `npm install --package-lock-only
   --ignore-scripts` in `sdk/typescript`). Add a changelog fragment.
2. **Merge** it (to `develop`, or to the `release/X.Y` branch the SDK release is cut
   from).
3. **Tag** the merge commit and push the tag. The tag's version must equal the
   package's version, or the workflow fails before building:

   ```bash
   git checkout develop && git pull
   git tag -a sdk-py-v0.1.0 -m "Python SDK 0.1.0"   # or sdk-ts-v0.1.0
   git push origin sdk-py-v0.1.0
   ```

4. **Approve the environment.** The tag starts
   [Publish SDK](.github/workflows/publish-sdk.yml): its build job runs the SDK's
   tests, builds the package, checks it (`twine check`, or the `npm pack` file
   list in the log) and keeps it as a run artifact. The publish job waits for a
   reviewer of the `pypi` or `npm` environment. Check the build log, then approve.
   The publish job runs no repository code: it downloads the built package, checks
   its name and version, and uploads it with trusted publishing (GitHub OIDC, no
   stored token). PyPI gets attestations, npm gets provenance.

A published version cannot be replaced, on either registry. If a release is broken,
release the next patch version.

Setup, done once by the owner of the PyPI and npm accounts:

- **PyPI:** a trusted publisher (a pending one until the first upload) for the
  project `bettercollected`: owner `bettercollected`, repository
  `bettercollected`, workflow `publish-sdk.yml`, environment `pypi`.
- **npm:** the organisation `bettercollected` (2FA for every member). Trusted
  publishing can only be set up on a package that exists, so the first release
  uses a granular token that can publish only `@bettercollected/sdk` and expires
  within days, stored as the secret `NPM_TOKEN` in the `npm` environment. The
  workflow passes it to npm only when it is set. After the first release: on
  npmjs.com, add the trusted publisher (repository
  `bettercollected/bettercollected`, workflow `publish-sdk.yml`, environment
  `npm`), set the package to require 2FA and disallow tokens, and delete the
  secret and the token. From then on npm authenticates with GitHub OIDC only.
- **GitHub:** the environments `pypi` and `npm`, each with a required reviewer
  and a deployment rule that allows only tags matching `sdk-*`.

## Future automation

Candidates when the cadence justifies it: `release-please` or
`semantic-release` to derive versions and changelog entries from Conventional
Commits automatically. Not adopted yet to keep the monorepo release process
transparent and low-magic.
