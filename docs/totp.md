# Authenticator app (TOTP) as a second factor

People who sign in to the dashboard (workspace members and owners) can add an authenticator app to their account, and a workspace owner can require one of every member. It is behind `TOTP_ENABLED` (`true` / `false`, default `false`; [settings inventory](settings-inventory.md)). Respondents, API keys and the MCP server are not covered, and the separate platform admin portal keeps its own second factor.

## What it is

- One authenticator app per account (RFC 6238: six digits, 30 second steps, SHA-1, one step of clock drift either way) and ten one-time recovery codes. The factor belongs to the **account**, not to a workspace.
- Setting it up (account settings, Security): scan the QR code or type the key, enter the first code, then store the ten recovery codes: they are shown once and never again. A setup that is not confirmed within 15 minutes is dropped.
- Starting a setup needs a session younger than 15 minutes (otherwise sign in again), so a stolen older cookie cannot plant its own authenticator. An account that already has one presents a current code to replace it, to make new recovery codes or to turn it off.
- Every change is mailed to the account (English or Dutch): app added, turned off, a recovery code used (and how many are left), the step locked, removed by an owner or by an administrator.

## Signing in

An account with an app is asked for a code after its **first factor** (email code or Google), before any session exists:

1. The first factor passes. No session is created; the browser gets a short-lived (5 minute) signed *challenge* cookie, valid for nothing else. The email-code answer is `{"mfaRequired": true}`; the Google callback redirects to the login page with `?mfa=1`.
2. The person enters a code from the app, or a recovery code. The session is created, records how it was presented and its tokens carry it.
3. Recovery codes work once each, are not mailed and not logged; using one is audited and mailed.

Single sign-on sessions are not asked (the identity provider's own policy applies), nor are respondent-scoped sessions. The second factor is presented **once per session**; refreshing a session keeps it. Fresh codes are only asked for sensitive changes.

### Limits

Guesses are limited before a code is evaluated, shared by setup, sign-in and recovery codes: five per five minutes per account however many arrive at once; a correct code gives its slot back. The fifth wrong code locks the second-factor step; each lock before a correct code lasts longer (15 minutes, 1 hour, 6 hours, 24 hours) and a correct code starts over. A code, or an earlier step, that was used is refused (replay). Twenty wrong codes from one client address in ten minutes also stop that address.

## Workspace rule: require an authenticator app

Owners (only) can require an authenticator app for all members of a workspace (Workspace settings, Security). The setting is checked on **every request** that reaches the workspace, like "require single sign-on":

- A member's session that has not presented a second factor gets 403 `mfa_required` and is sent to enter the code or set one up **in the same session**; nobody is signed out.
- Not covered: API keys and MCP (machine credentials issued inside the workspace), respondent-scoped sessions, and a single sign-on session that signed in through this workspace's own identity provider.
- Turning it on needs the owner's own session to have presented a second factor, so an owner cannot lock themselves out. The owners see "N of M members have set one up" before confirming. Turning it off takes effect on the next request.
- A person cannot turn their own app off while a workspace they belong to requires one.
- Nothing is read beyond what authorisation already reads (the workspace and the session's claim).

## Lost device and resets

- A person who lost the device signs in with a recovery code and then makes new ones.
- **An owner** can remove a member's app (member list, "Reset second factor") **only** for a member whose address is on one of the workspace's verified domains, or who belongs to no other workspace. Otherwise the answer is `reset_not_allowed`: the person's account reaches another workspace, so the person recovers with a recovery code or asks the administrator of the service. Nobody resets their own.
- **The platform administrator** can remove anyone's (`DELETE /admin/users/{id}/totp`; the `ADMIN` role, never an SSO session).
- A reset deletes the factor and its recovery codes, ends all of that person's sessions, mails them and is audited with the ids of the person who did it and the account it was done to.

## Turning the switch off (the downgrade)

`TOTP_ENABLED=false` makes the whole feature inert at once; **nothing is deleted**:

- Nobody is asked for a second factor at sign-in, not even accounts that have an app.
- No workspace rule is enforced (the stored setting stays, and applies again if the switch goes back on).
- The routes answer 422 `totp_off`; the member list has no column.
- Sessions that already presented a factor keep their claim until they end.

This **removes protection that people and workspace owners were relying on**. Before turning it off on an instance where workspaces require an app, tell the owners. Turning it back on brings back the challenge for every account that still has an app, and the workspace rules, on the next request.

## For operators

- The secret of an app is sealed with `AUTH_AES_HEX_KEY` (a Fernet key ring) inside an envelope bound to the account and the factor; it is never logged, returned after setup or shown in an audit row. The `authkeys.*` rotation tasks cover it ([auth-key-rotation.md](auth-key-rotation.md)). **The rotation change must be deployed, and `authkeys.verify` must report no unopenable value, before `TOTP_ENABLED` is turned on**; otherwise `drop_old` could strand sealed secrets.
- Recovery codes are stored as an unkeyed SHA-256 bound to the account (80 random bits each), so a key rotation does not affect them.
- Tables (Postgres only): `user_totp_factors`, `user_recovery_codes`. The workspace rule is a field of the workspace document. Sessions record `mfa_at` and `mfa_method`; tokens carry `mfa`, only ever set by the backend from the session's record.
- The challenge cookie is signed with the access key ring and carries an audience, so no access-token decoder (backend, auth, the Google service) accepts it.
- Audit entries (`app.workspace_audit_events`, kept for a year): `totp_enrolled`, `totp_removed`, `totp_reset`, `totp_recovery_used`, `totp_recovery_regenerated`, `totp_locked`, `totp_policy_changed`. Ids only: never a code, a secret or an address.
- The mails come from the auth service (`POST /notifications/security`, internal key only; the wording is fixed in `mail_text.py`, the recipient is found from the account id). They are sent in the background, once, after the change.
- Clocks: servers should run NTP. A person whose phone clock is off by more than about 30 seconds gets "not valid" (the answer is always the same, never "wrong by one step").
- Daily job `totp_pending_purge` deletes setups never confirmed. Deleting an account deletes its factor.

## API

See the routes in the OpenAPI document: `/auth/mfa/*` (status, setup, confirm, verify, recovery codes, turn off, the sign-in challenge), `/workspaces/{id}/security/totp` (GET, PUT), `/workspaces/{id}/members/{userId}/totp` (DELETE), `/admin/users/{userId}/totp` (DELETE). Errors carry a `code` (`totp_off`, `recent_proof_required`, `invalid_code`, `too_many_attempts`, `mfa_locked`, `no_factor`, `enrol_first`, `mfa_required`, `reset_not_allowed`, `reset_self`, `required_by_workspace`, `mfa_challenge_expired`).

## Tests

`backend/tests/app/mfa/` (setup, codes and limits, sign-in, the claim on every token, the workspace rule, resets and mails), `backend/tests/admin/tasks/test_authkeys_tasks.py` (rotation), `auth/tests/integration/app/controllers/test_security_notice.py` (mails).
