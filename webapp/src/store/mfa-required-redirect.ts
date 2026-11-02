import { Middleware, isRejectedWithValue } from '@reduxjs/toolkit';

import { isDashboardPath } from '@app/store/sso-required-redirect';

/** The backend's refusal of a session that has not presented a second factor where the workspace requires one. */
export function isMfaRequiredError(error: unknown): boolean {
    const failure = error as { status?: unknown; data?: { code?: unknown } } | null | undefined;
    return failure?.status === 403 && failure?.data?.code === 'mfa_required';
}

/** The page that asks for the second factor (or sets one up), for a workspace; `next` is where to go afterwards. */
export function mfaVerifyUrl(pathname: string): string | null {
    const match = /^\/([^/]+)\/(dashboard|onboarding)(\/|$)/.exec(pathname);
    if (!match) return null;
    return `/${match[1]}/security/verify`;
}

export const mfaNavigation = {
    goTo: (url: string) => window.location.assign(url)
};

let navigating = false;

/** Forget a navigation in progress (a page restored from the back/forward cache, tests). */
export function resetMfaRedirect() {
    navigating = false;
}

if (typeof window !== 'undefined') {
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) resetMfaRedirect();
    });
}

/**
 * Any staff API call refused with 403 `mfa_required` (the workspace requires an
 * authenticator app and this session has not presented one: docs/totp.md) sends
 * the browser to that workspace's verify page, which asks for the code or sets
 * an app up in the same session, then returns to the page the person was on.
 * Nobody is signed out. Like the single sign-on redirect it acts only from a
 * dashboard page, and the verify page itself is not one, so it cannot loop.
 */
export const mfaRequiredRedirect: Middleware = () => (next) => (action) => {
    if (!navigating && typeof window !== 'undefined' && isRejectedWithValue(action) && isMfaRequiredError(action.payload) && isDashboardPath(window.location.pathname)) {
        const verify = mfaVerifyUrl(window.location.pathname);
        if (verify) {
            // several requests of one page are refused together: one navigation
            navigating = true;
            const back = `${window.location.pathname}${window.location.search}`;
            mfaNavigation.goTo(`${verify}?next=${encodeURIComponent(back)}`);
        }
    }
    return next(action);
};
