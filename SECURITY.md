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

## Secrets and Credentials

Never commit real secrets (API keys, tokens, passwords, private keys) to this
repository. All `.env.example` files must contain **placeholders only**. If you
discover a committed secret, please report it privately using the channels above
so it can be rotated and removed from history.
