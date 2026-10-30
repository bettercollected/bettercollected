import { NextRequest, NextResponse } from 'next/server';

import environments from '@app/configs/environments';

/**
 * A link to a workspace dashboard page opened without a session goes to the
 * sign-in page, which brings the user back to that page afterwards (when
 * they are a member there; the server decides, see the sign-in page). Only
 * the presence of a session cookie is looked at here: every page still checks
 * the session and the membership itself.
 *
 * The redirect names the configured scheme and dashboard domain (the host
 * the request came to, checked first) under the deploy base path, never the
 * address the app itself listens on. `redirect_to` stays a path of the app
 * without the base path, like every other sign-in target (`usePathname()`):
 * the sign-in page's `redirect()` adds the base path itself.
 */
export function signInRedirect(request: NextRequest): NextResponse | null {
    const host = request.headers.get('x-forwarded-host') || request.headers.get('host') || '';
    if (host !== environments.DASHBOARD_DOMAIN) return null;
    if (request.cookies.has('Authorization') || request.cookies.has('RefreshToken')) return null;
    const { pathname, search } = request.nextUrl;
    const login = new URL(`${dashboardScheme()}://${environments.DASHBOARD_DOMAIN}${deployBasePath()}/login`);
    login.searchParams.set('redirect_to', `${pathname}${search}`);
    return NextResponse.redirect(login, 307);
}

/** `HTTP_SCHEME` ("https://" or "http://"); https for anything else. */
function dashboardScheme(): 'http' | 'https' {
    const scheme = (environments.HTTP_SCHEME || '').replace(/:\/\/$/, '').toLowerCase();
    return scheme === 'http' ? 'http' : 'https';
}

/** next.config.js's basePath (BASE_DEPLOY_PATH): "" or "/prefix". */
function deployBasePath(): string {
    const base = (process.env.BASE_DEPLOY_PATH || '').trim().replace(/\/+$/, '');
    return base && base.startsWith('/') ? base : '';
}

export function proxy(request: NextRequest) {
    return signInRedirect(request) ?? NextResponse.next();
}

export const config = {
    matcher: ['/:workspace_name/dashboard', '/:workspace_name/dashboard/:path*']
};
