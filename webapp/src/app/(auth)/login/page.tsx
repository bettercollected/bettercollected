import { isRedirectError } from 'next/dist/client/components/redirect-error';
import { cookies, headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import environments from '@app/configs/environments';
import { getWorkspaceSelection } from '@app/lib/server/api';
import { SELECT_WORKSPACE_PATH, postSignInDestination } from '@app/lib/workspace-selection';
import { SERVER_PATH_ORIGIN, isSameSitePath } from '@app/utils/same-site-path';

import LoginView from '../_components/login-view';

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ redirect_to?: string | string[]; type?: string; workspace_id?: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const cookieStore = await cookies();
    const authCookie = cookieStore.get('Authorization');
    const refreshCookie = cookieStore.get('RefreshToken');
    const cookieHeader = `${authCookie ? `Authorization=${authCookie.value};` : ''}${refreshCookie ? `RefreshToken=${refreshCookie.value};` : ''}`;

    // where the sign-in started: a path of this app only, never an address elsewhere
    const { redirect_to } = await searchParams;
    const requested = Array.isArray(redirect_to) ? redirect_to[0] : redirect_to;
    const target = isSameSitePath(requested, SERVER_PATH_ORIGIN) ? requested : undefined;

    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            method: 'GET',
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (userStatus.ok) {
            if (host === environments.DASHBOARD_DOMAIN) {
                // The server says which workspaces this user may open and
                // whether the page the sign-in started from is one of them.
                const selection = await getWorkspaceSelection(target);
                return redirect(selection ? postSignInDestination(selection) : SELECT_WORKSPACE_PATH);
            } else {
                if (target) redirect(target);
                else notFound();
            }
        }
    } catch (e) {
        if (isRedirectError(e)) {
            throw e;
        }
        console.error('Error during server-side auth check:', e);
    }

    return <LoginView />;
}
