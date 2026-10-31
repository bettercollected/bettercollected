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

The deployment compose file runs `bettercollected/<service>:${BC_IMAGE_TAG:-vX.Y.Z}`, so a
self-hoster who has not chosen a tag gets the latest release, not `nightly`. Set that default
to the new version in the changelog PR of step 2 (`docker-compose.deployment.yml`, every
`BC_IMAGE_TAG` default); a test fails until it equals the newest version in CHANGELOG.md.

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

### Setup, done once by the owner, before the first tag

The environments must exist **with their protection rules** before any `sdk-*` tag
is pushed: when a job names an environment that does not exist, GitHub creates it
without any rules, and the publish job would then run without approval.

- **GitHub environments** `pypi` and `npm` (Settings → Environments), each with:
  - a required reviewer (optionally with "Prevent self-review", so the person who
    pushed the tag cannot approve it; with a single maintainer that blocks releases);
  - deployment branches and tags limited to "Selected branches and tags", with one
    tag rule: `sdk-py-v*` for `pypi`, `sdk-ts-v*` for `npm`.
- **GitHub tag ruleset** (Settings → Rules → Rulesets, recommended): a tag ruleset
  targeting `sdk-*` and `v*` that restricts creations, updates and deletions, with
  only maintainers or admins in the bypass list. A tag runs the workflow file of the
  tagged commit, so this limits who can start a release at all.
- **PyPI:** a trusted publisher (a pending one until the first upload) for the
  project `bettercollected`: owner `bettercollected`, repository
  `bettercollected`, workflow `publish-sdk.yml`, environment `pypi`.
- **npm**, trusted publishing only (no npm token is ever stored). Trusted
  publishing can only be set up on a package that exists, and a new trusted
  publisher must complete its first publish within 2 days, so, in this order:
  1. The organisation `bettercollected` exists on npmjs.com (2FA for every member).
  2. Publish a placeholder `@bettercollected/sdk@0.0.1` by hand (a package that
     only reserves the name and points to 0.1.0 and later), then deprecate it:
     `npm deprecate @bettercollected/sdk@0.0.1 "Name reserved; use 0.1.0 or later"`.
  3. In the package's settings on npmjs.com, Trusted publishing → GitHub Actions:
     organisation or user `bettercollected`, repository `bettercollected`, workflow
     `publish-sdk.yml`, environment `npm`. Allow it to run `npm publish` (not only
     staged publishing).
  4. Optionally, set the package's publishing access to "Require two-factor
     authentication and disallow tokens". Trusted publishing keeps working.
  5. Push the tag `sdk-ts-v0.1.0` (see below) within 2 days of step 3.

  The `npm` environment's rules (required reviewer, `sdk-ts-v*` tag rule) are still
  required: they decide which runs may ask for the OIDC token npm trusts. The
  publish job checks that it runs Node 22.14.0 or later and npm 11.5.1 or later,
  which trusted publishing needs.

### Releasing an SDK

The workflow exists only on the branches this setup was merged to (`develop`,
`release/4.1` and later). A tag on a commit without it does nothing.

1. **Bump the version** in a pull request: `version` in `sdk/python/pyproject.toml`
   (then `uvx uv@0.12.23 lock` in `sdk/python`), or `version` in
   `sdk/typescript/package.json` (then `npm install --package-lock-only
   --ignore-scripts` in `sdk/typescript`). Add a changelog fragment.
2. **Merge** it (to `develop`, or to the `release/X.Y` branch the SDK release is cut
   from).
3. **Tag the merge commit** and push the tag. Check out the branch you merged to,
   take the merge commit's sha, and name it in the tag. The tag's version must equal
   the package's version, or the workflow fails before building:

   ```bash
   git checkout develop && git pull            # or release/X.Y
   git log --oneline -3                        # the merge commit of step 2
   git tag -a sdk-py-v0.1.0 <merge-sha> -m "Python SDK 0.1.0"   # or sdk-ts-v0.1.0
   git push origin sdk-py-v0.1.0
   ```

4. **Check, then approve the environment.** The tag starts
   [Publish SDK](.github/workflows/publish-sdk.yml): its build job runs the SDK's
   tests, builds the package, checks it (`twine check`, or the `npm pack` file
   list in the log) and keeps it as a run artifact for 7 days. The publish job waits
   for a reviewer of the `pypi` or `npm` environment. Before approving, confirm on
   the run's commit (`<sha>`, shown on the run page) that:

   - it is on `develop` or a `release/X.Y` branch:

     ```bash
     git fetch origin
     git branch -r --contains <sha>   # lists origin/develop or origin/release/X.Y
     # or: gh api repos/bettercollected/bettercollected/compare/develop...<sha> -q .status
     #     ("identical" or "behind" means the commit is on develop)
     ```

   - its workflow file is the one on that branch (no output means equal):

     ```bash
     git diff --exit-code origin/develop <sha> -- .github/workflows/publish-sdk.yml   # or origin/release/X.Y
     ```

   Then check the build log and approve. The publish job runs no repository code: it
   downloads the built package, checks its name, version and digest, and uploads it
   with trusted publishing (GitHub OIDC, no stored token). PyPI gets attestations,
   npm gets provenance. If more than 7 days pass before approval, the artifact is
   gone: re-run all jobs of the run.

A published version cannot be replaced, on either registry. If a release is broken,
release the next patch version.

## Future automation

Candidates when the cadence justifies it: `release-please` or
`semantic-release` to derive versions and changelog entries from Conventional
Commits automatically. Not adopted yet to keep the monorepo release process
transparent and low-magic.
