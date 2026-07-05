# Project Governance

This document describes how the **bettercollected** open-source project is run.
It is deliberately lightweight; we will formalise it further as the community
grows.

## Roles

### Users

Anyone who uses bettercollected. Users contribute by filing issues, joining
discussions, and helping others. No permissions required.

### Contributors

Anyone who submits a pull request, issue, or documentation improvement. All
contributions go through the process in [CONTRIBUTING.md](CONTRIBUTING.md) and
are subject to the [Code of Conduct](CODE_OF_CONDUCT.md).

### Maintainers

Maintainers review and merge pull requests, triage issues, steer the
[roadmap](ROADMAP.md), and cut releases. They have write access to the
repository and are listed as owners in [.github/CODEOWNERS](.github/CODEOWNERS).

Current stewardship sits with the core team behind bettercollected. Maintainers
are added by consensus of the existing maintainers (see below).

## Decision making

We favour **lazy consensus**: a proposal (issue or PR) is accepted if no
maintainer objects within a reasonable review window. Most changes need at least
**one maintainer approval** to merge; larger or cross-service changes should get
review from an owner of each affected area.

When consensus can't be reached, maintainers decide by simple majority. The
goal is always to find the option that best serves users' privacy and the health
of the project.

## Becoming a maintainer

We invite active contributors to become maintainers based on a track record of:

- High-quality contributions across more than a one-off change,
- Helpful, respectful participation in reviews and discussions,
- Good judgment about the project's scope and privacy-first values.

Any maintainer may nominate a contributor; the addition proceeds by lazy
consensus of the existing maintainers.

## Changing this document

Amendments follow the same PR + review process as code. Substantive governance
changes should be open for comment for at least a week before merging.
