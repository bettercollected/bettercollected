import { NextRequest, NextResponse } from 'next/server';

import environments from '@app/configs/environments';
import { frameAncestorsFor } from '@app/lib/frame-ancestors';

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

const DASHBOARD_PATH = /^\/[^/]+\/dashboard(\/|$)/;

/**
 * Two jobs, both at request time (next.config.js `headers()` is evaluated when the image is built, without
 * the running server's domains, which is how the old `X-Frame-Options: ALLOW-FROM` named an undefined host):
 * a link to a dashboard page without a session goes to sign-in, and every page except a published form's
 * says who may frame it (lib/frame-ancestors.ts). The matcher covers every route but `_next/` and files
 * with a static-file extension (a workspace handle may contain a dot), the 404 page included. The proxy is the only place this header is set.
 */
export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl;
    const response = (DASHBOARD_PATH.test(pathname) ? signInRedirect(request) : null) ?? NextResponse.next();
    const value = frameAncestorsFor(pathname, `${dashboardScheme()}://${environments.DASHBOARD_DOMAIN}`);
    if (value) response.headers.set('Content-Security-Policy', value);
    return response;
}

export const config = {
    matcher: ['/((?!_next/|.*\\.(?:png|jpe?g|gif|svg|ico|webp|avif|css|js|mjs|map|json|txt|xml|woff2?|ttf|otf|webmanifest|mp4|pdf)$).*)']
};
