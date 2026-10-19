# Security Policy

We take the security of bettercollected and its users' data seriously.
bettercollected is a privacy-focused form builder, so responsible disclosure of
vulnerabilities is especially important to us.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, report them privately through one of these channels:

1. **GitHub Security Advisories** (preferred) — open a private report via the
   repository's **Security → Advisories → Report a vulnerability** page.
2. **Email** — send details to **security@bettercollected.com**.

Please include as much of the following as you can:

- The affected service (`webapp`, `backend`, `auth`, `integrations/*`,
  `temporal/*`) and version/commit
- A description of the vulnerability and its impact
- Steps to reproduce (a proof of concept is very helpful)
- Any suggested remediation

## What to Expect

- We aim to acknowledge your report within **3 business days**.
- We will keep you informed as we investigate and work on a fix.
- We will credit you in the release notes once the issue is resolved, unless you
  prefer to remain anonymous.
- Please give us a reasonable window to release a fix before any public
  disclosure.

## Scope

In scope:

- The application code in this repository (all services listed above)
- Authentication, authorization, consent, and data-deletion flows
- Handling of encrypted secrets and OAuth credentials

Out of scope:

- Vulnerabilities in third-party dependencies that already have a published
  advisory — please instead ensure they are picked up by Dependabot
  (see [`.github/dependabot.yml`](.github/dependabot.yml)).
- The hosted cloud service infrastructure (report those directly to us).

## Internal admin portal

The repository includes an internal admin portal (`docs/admin-service.md`). A summary of its threat model:

- It is reachable from the host only: the port is published on the loopback interface and the service checks the
  client address and `Host` header against allowlists.
- Signing in needs two factors: a code mailed to a listed administrator and a code from an authenticator (or a
  recovery code). Sessions are bound to the address and browser, are short-lived and can be revoked.
- State-changing requests need a CSRF token and a same-origin check; pages send a strict content security policy
  and contain no inline script or style.
- Every sign-in, change and refusal is written to an append-only audit log chained with a keyed hash;
  `python -m backend.admin audit-verify` recomputes the chain. Secret values are never shown in pages or logs.
- The database role it uses can read and write only its own schemas; it cannot read application data except
  through two read-only functions that return counts.
- The break-glass path is the host command line (`python -m backend.admin`): unlock an address, lift the sign-in
  pause, revoke sessions, or remove a lost second factor. Each is audited, and a factor reset also mails every administrator. There is
  no email-only reset.
- `SETTINGS_MASTER_KEY` cannot be recovered. Keep a backup of it separate from the server.

## Secrets and Credentials

Never commit real secrets (API keys, tokens, passwords, private keys) to this
repository. All `.env.example` files must contain **placeholders only**. If you
discover a committed secret, please report it privately using the channels above
so it can be rotated and removed from history.
