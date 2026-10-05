// Enterprise single sign-on (docs/sso.md). Whether it is on comes from the
// webapp's SSO_ENABLED at runtime: useSsoEnabled() in
// @app/shared/hocs/runtime-flags-provider.

// The backend sends the browser back with a fixed code, never free text, and
// anyone can craft the URL: only these codes are explained, anything else
// gets the generic message.
export const ssoErrorMessages: Record<string, string> = {
    sso_disabled: 'Single sign-on is not enabled.',
    sso_not_configured: "Single sign-on isn't set up for this email domain. Sign in another way, or ask your workspace admin.",
    sso_email_domain_not_allowed: "Your identity provider signed you in with an email address this workspace's single sign-on doesn't cover.",
    sso_workspace_unavailable: 'The workspace for this sign-in is not available.',
    sso_seat_limit: 'This workspace has no free seats for another member. Ask a workspace admin to free a seat.',
    sso_account_conflict: 'More than one account uses this email address. Contact support to have them merged.',
    sso_tenant_mismatch: 'Single sign-on failed. Please try again.',
    sso_session_mismatch: 'This sign-in was started in another browser or was already used. Please start again.',
    sso_membership_disabled: 'Your membership of this workspace is disabled. Ask a workspace admin.',
    sso_deprovisioned: "Your organisation's directory has deactivated your access to this workspace. Ask your IT admin.",
    sso_expired: 'The sign-in took too long. Please try again.',
    sso_failed: 'Single sign-on failed. Please try again.'
};

export function ssoErrorMessage(code?: string | null): string | null {
    if (!code) return null;
    return ssoErrorMessages[code] ?? ssoErrorMessages.sso_failed;
}

// Outcome of "Test connection" (``sso_test=`` on the settings page).
export const ssoTestMessages: Record<string, string> = {
    ok: 'The test sign-in worked: your identity provider vouched for an address on one of your verified domains.',
    sso_email_domain_not_allowed: 'Your identity provider signed you in with an address that is not on one of this workspace’s verified domains. Check the email attribute your identity provider sends, or verify that domain.',
    sso_tenant_mismatch: 'The identity provider answered for another connection. Try again; if it keeps happening, delete and re-create the connection.',
    sso_test_not_allowed: 'Only the admin who started the test can complete it. Start the test again while signed in.',
    sso_session_mismatch: 'The test was started in another browser or was already used. Start it again.',
    sso_workspace_unavailable: 'This workspace is not available.',
    sso_expired: 'The test took too long. Please try again.',
    sso_failed: 'The identity provider did not complete the sign-in. Check the connection details at your identity provider and try again.'
};

export function ssoTestMessage(code?: string | null): string | null {
    if (!code) return null;
    return ssoTestMessages[code] ?? ssoTestMessages.sso_failed;
}

/** Full-page navigation that sends a full Referer, so the backend can send the
 * browser back to this page afterwards (only to this instance's origins). */
export function navigateWithReferrer(url: string) {
    const link = document.createElement('a');
    link.href = url;
    link.referrerPolicy = 'unsafe-url';
    document.body.appendChild(link);
    link.click();
    link.remove();
}
