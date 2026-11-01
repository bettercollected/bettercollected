import { NextRequest, NextResponse } from 'next/server';

import environments from '@app/configs/environments';
import { ASSERTION_HEADER, customDomainTarget } from '@app/lib/server/custom-domain';
import { EmbedPolicy, PolicyQuery, fetchEmbedPolicy, frameAncestorsValue } from '@app/lib/server/embed-policy';

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
// A published form's page: /<workspace>/forms/<form> (the client domain, also its /preview, which the
// builder frames) and /forms/<form> on a custom domain.
const FORM_DOMAIN_FORM_PATH = /^\/([^/]+)\/forms\/[^/]+(\/preview)?\/?$/;
const CUSTOM_DOMAIN_FORM_PATH = /^\/forms\/[^/]+\/?$/;

function requestHost(request: NextRequest): string {
    return request.headers.get('x-forwarded-host') || request.headers.get('host') || '';
}

/** Which workspace's policy a request for a published form's page is answered with, or null for any other page. */
export function embedPolicyQuery(request: NextRequest): { query: PolicyQuery | null } | null {
    const host = requestHost(request);
    const { pathname } = request.nextUrl;
    if (host === environments.DASHBOARD_DOMAIN) return null;
    if (host === environments.FORM_DOMAIN) {
        const match = FORM_DOMAIN_FORM_PATH.exec(pathname);
        if (!match) return null;
        try {
            return { query: { workspace_name: decodeURIComponent(match[1]) } };
        } catch {
            return { query: null };
        }
    }
    if (!CUSTOM_DOMAIN_FORM_PATH.test(pathname)) return null;
    // The workspace is chosen exactly as the page's layout chooses it: by the edge's verified assertion.
    const target = customDomainTarget(host, request.headers.get(ASSERTION_HEADER));
    if (target.kind === 'workspaceId') return { query: { workspace_id: target.workspaceId } };
    if (target.kind === 'host') return { query: { custom_domain: target.host } };
    return { query: null };
}

function withFrameAncestors(response: NextResponse, value: string | null): NextResponse {
    if (value) response.headers.set('Content-Security-Policy', value);
    return response;
}

function dashboardOrigin(): string {
    return `${dashboardScheme()}://${environments.DASHBOARD_DOMAIN}`;
}

/**
 * Framing, by page. The dashboard is never framed by another site (`frame-ancestors 'self'`). A published
 * form's page is answered from the workspace's embed policy (docs/embed.md): with the server's switch off
 * no header at all (as before); on, this site, the dashboard's preview and the workspace's allowed sites.
 * The sign-in redirect stays dashboard-only.
 */
export function proxy(request: NextRequest): NextResponse | Promise<NextResponse> {
    const { pathname } = request.nextUrl;
    if (DASHBOARD_PATH.test(pathname)) {
        return withFrameAncestors(signInRedirect(request) ?? NextResponse.next(), "frame-ancestors 'self'");
    }
    const target = embedPolicyQuery(request);
    if (!target) return NextResponse.next();
    return answerForm(target.query);
}

async function answerForm(query: PolicyQuery | null): Promise<NextResponse> {
    const policy: EmbedPolicy | null = query ? await fetchEmbedPolicy(query) : null;
    return withFrameAncestors(NextResponse.next(), frameAncestorsValue(policy, dashboardOrigin()));
}

export const config = {
    matcher: ['/:workspace_name/dashboard', '/:workspace_name/dashboard/:path*', '/:workspace_name/forms/:form_id', '/:workspace_name/forms/:form_id/preview', '/forms/:form_id']
};
