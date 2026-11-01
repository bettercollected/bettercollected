import { Middleware, isRejectedWithValue } from '@reduxjs/toolkit';

import { SSO_REQUIRED_NOTICE, selectWorkspaceUrl } from '@app/lib/workspace-selection';

/** The backend's refusal of a session that doesn't meet a workspace's single sign-on requirement. */
export function isSsoRequiredError(error: unknown): boolean {
    const failure = error as { status?: unknown; data?: { code?: unknown } } | null | undefined;
    return failure?.status === 403 && failure?.data?.code === 'sso_required';
}

/** A page of a workspace's dashboard (or its onboarding): where the staff API calls are made. */
export function isDashboardPath(pathname: string): boolean {
    return /^\/[^/]+\/(dashboard|onboarding)(\/|$)/.test(pathname);
}

/** The browser's navigation, in one place a test can replace. */
export const navigation = {
    goTo: (url: string) => window.location.assign(url)
};

let navigating = false;

/** Forget a navigation in progress (a page restored from the back/forward cache, tests). */
export function resetSsoRedirect() {
    navigating = false;
}

if (typeof window !== 'undefined') {
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) resetSsoRedirect();
    });
}

/**
 * Any API call the backend refuses with 403 `sso_required` (the workspace
 * requires single sign-on and this session didn't use it: docs/sso.md) sends
 * the browser to the workspace selection, whose row for that workspace starts
 * its SSO sign-in. One place for every API slice, instead of a generic 403 in
 * each. Only from a dashboard page: the workspace's public pages (where the
 * same session may still answer forms) and the selection screen itself (so it
 * can never loop) are left alone.
 */
export const ssoRequiredRedirect: Middleware = () => (next) => (action) => {
    if (!navigating && typeof window !== 'undefined' && isRejectedWithValue(action) && isSsoRequiredError(action.payload) && isDashboardPath(window.location.pathname)) {
        // several requests of one page are refused together: one navigation
        navigating = true;
        navigation.goTo(selectWorkspaceUrl(SSO_REQUIRED_NOTICE));
    }
    return next(action);
};
