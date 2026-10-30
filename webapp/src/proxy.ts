import { NextRequest, NextResponse } from 'next/server';

import environments from '@app/configs/environments';

/**
 * A link to a workspace dashboard page opened without a session goes to the
 * sign-in page, which brings the user back to that page afterwards (when
 * they are a member there; the server decides, see the sign-in page). Only
 * the presence of a session cookie is looked at here: every page still checks
 * the session and the membership itself.
 *
 * The redirect names the configured dashboard domain (the host the request
 * came to, checked first), never the address the app itself listens on.
 */
export function signInRedirect(request: NextRequest): NextResponse | null {
    const host = request.headers.get('x-forwarded-host') || request.headers.get('host') || '';
    if (host !== environments.DASHBOARD_DOMAIN) return null;
    if (request.cookies.has('Authorization') || request.cookies.has('RefreshToken')) return null;
    const { pathname, search } = request.nextUrl;
    const forwardedProto = request.headers.get('x-forwarded-proto')?.split(',')[0].trim();
    const protocol = forwardedProto === 'http' || forwardedProto === 'https' ? forwardedProto : request.nextUrl.protocol.replace(':', '');
    // the configured dashboard domain (checked above), never an internal host
    const login = new URL(`${protocol}://${environments.DASHBOARD_DOMAIN}/login`);
    login.searchParams.set('redirect_to', `${pathname}${search}`);
    return NextResponse.redirect(login, 307);
}

export function proxy(request: NextRequest) {
    return signInRedirect(request) ?? NextResponse.next();
}

export const config = {
    matcher: ['/:workspace_name/dashboard', '/:workspace_name/dashboard/:path*']
};
