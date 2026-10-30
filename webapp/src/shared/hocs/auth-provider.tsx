import { unstable_rethrow } from 'next/navigation';
import React, { Suspense } from 'react';

import AuthDispatcher from '@app/app/_dispatcher/auth-dispatcher';
import environments from '@app/configs/environments';
import { fetchWithCookiesResponse } from '@app/utils/fetch-utils';
import { ServerAuthAnswer, readServerAuthAnswer } from '@app/utils/session-answer';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';

/**
 * Who is signed in, by the status code as well as the body: only a 401 says
 * that nobody is; a 5xx or an HTML error page (or the backend out of reach)
 * is "unknown", which must not sign anyone out (utils/session-answer).
 */
export async function fetchAuthState(): Promise<ServerAuthAnswer> {
    try {
        const response = await fetchWithCookiesResponse(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/auth/status', { method: 'GET', cache: 'no-store' });
        const isJson = response.headers.get('content-type')?.includes('application/json');
        const body = isJson ? await response.json().catch(() => null) : null;
        return readServerAuthAnswer(response.status, body);
    } catch (error) {
        // Next's own signals (dynamic rendering, redirects) must go through
        unstable_rethrow(error);
        return { kind: 'unknown' };
    }
}

export default async function AuthProvider({ children }: { children: React.ReactNode }) {
    const auth = await fetchAuthState();
    return (
        <Suspense fallback={<FullScreenLoader />}>
            <AuthDispatcher auth={auth}>{children}</AuthDispatcher>
        </Suspense>
    );
}
