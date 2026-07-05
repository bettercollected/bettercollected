# Roadmap

This is a **living document** that captures the direction of the project. It is
intentionally high-level — specifics are tracked in
[issues](https://github.com/bettercollected/bettercollected/issues) and
milestones. Priorities can shift; nothing here is a commitment or a dated
promise.

Want to influence it? Open an issue or a discussion, or pick up something below.

## Vision

A privacy-friendly, open-source form builder that makes **purpose, consent, and
data-deletion** first-class — so creators can collect responsibly and responders
stay in control of their data.

## Now — stabilise the open-source foundation

The current focus is making the project easy and trustworthy to contribute to
after the recent monorepo migration (uv, Pydantic v2, Next 16).

- Keep dependencies healthy via Dependabot; keep security alerts at zero.
- Grow automated test coverage and keep CI green across services.
- Repay migration debt (e.g. fix the `integrations/google` test suite left
  broken by the Pydantic v1 → v2 migration; see
  [Known gaps](#known-gaps--tech-debt)).
- Fill remaining contributor-experience gaps (docs, templates, examples).

## Next — contributor & quality investments

- Expand the frontend test suite (component + integration coverage) beyond the
  initial smoke tests.
- Add lint / format / type-check gates to CI for all services.
- Re-introduce API contract testing (Schemathesis) in CI.
- A one-command local bootstrap for new contributors.
- Adopt a lightweight, documented release process (see [RELEASING.md](RELEASING.md)).

## Later — product & platform

- More form-builder field types and templates.
- Additional import/integration providers beyond Google Forms and Typeform.
- Deeper consent & GDPR tooling (data-retention policies, export formats).
- Internationalisation and accessibility improvements.

## Known gaps / tech debt

These are known and tracked; contributions welcome:

- **`integrations/google` tests** — broadly broken by the Pydantic v1 → v2
  migration (dead modules referencing a removed CLI/WSGI loader, plus outdated
  `pydantic.error_wrappers` imports). Not yet wired into CI for this reason.
- **Pydantic v2 deprecations** — several services still use v1-style
  `class Config` / `@root_validator`; these emit deprecation warnings.
- **Git history contains rotated secrets** — see the note in
  [SECURITY.md](SECURITY.md) / release notes; history scrubbing is a maintainer
  task.

---

_Last reviewed against the open-source readiness audit. Update this file as
priorities change._
