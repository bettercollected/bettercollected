# Changelog fragments

A pull request does not edit [CHANGELOG.md](../CHANGELOG.md). It adds its entry as a small
file here, so pull requests never conflict on the changelog. When a release is cut, the
fragments are moved into the release's section of CHANGELOG.md and deleted
(see [RELEASING.md](../RELEASING.md)).

## Naming

```
changelog.d/<pr-number-or-branch-slug>.<category>.md
```

- **Name**: the pull request number (`1052.fixed.md`) or, before the pull request exists,
  the branch name with `/` replaced by `-` (`fix-sso-orphaned-connections.fixed.md`).
  Letters, digits, `.`, `_` and `-`.
- **Category**: one of the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
  categories CHANGELOG.md uses: `added`, `changed`, `deprecated`, `removed`, `fixed`,
  `security`.
- A change that belongs under two categories gets two files (`1052.added.md` and
  `1052.fixed.md`).

## Content

The bullet or bullets exactly as they should appear in CHANGELOG.md, wrapped the same way:
each line starts a bullet (`- `) or continues one (indented). No headings, no blank lines.

```markdown
- Deleting an account now also erases its marketing contact. Without the key the
  erasure is skipped, and it never holds up the deletion.
```

Preview the next release's notes, with every fragment in place:

```bash
python3 -I .github/scripts/changelog.py assemble --draft
```

## Which pull requests need one

The `Changelog fragment` check in the PR checks fails when a pull request changes code,
configuration, deployment files or CI without adding a fragment. Changes to these alone
need none: `docs/**`, any `*.md` file, `changelog.d/`, `.github/ISSUE_TEMPLATE/`,
`.github/CODEOWNERS`, `.github/FUNDING.yml`, `AUTHORS`, and tests (files in a `tests/`,
`test/`, `__tests__/` or `__mocks__/` directory, `test_*.py`, `*_test.py`, `conftest.py`,
`*.test.*`, `*.spec.*`).

When a change needs no entry (an internal refactor, a CI tweak nobody running the software
notices), label the pull request `no-changelog`. Dependabot's pull requests are exempt; their
updates are noted when they are folded together.

The check also fails when a pull request edits CHANGELOG.md directly. Only a release's
changelog pull request does that, from a branch named `docs/changelog-X.Y.Z`.

Branch syncs are not checked: a pull request whose head is `develop`, `master`, `main`, a
`release/*` branch, or a merge-forward branch `merge/release-<x>-into-develop`. A
merge-forward brings a release branch's released CHANGELOG.md sections (and their changes)
into develop, so it edits CHANGELOG.md without a fragment (see RELEASING.md).
