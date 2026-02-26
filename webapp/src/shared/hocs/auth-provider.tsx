import React, { Suspense } from 'react';

import AuthDispatcher from '@app/app/_dispatcher/auth-dispatcher';
import environments from '@app/configs/environments';
import fetchWithCookies from '@app/utils/fetch-utils';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';

async function fetchAuthState() {
    const res = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/auth/status', { method: 'GET', cache: 'no-store' });
    return res;
}

export default async function AuthProvider({ children }: { children: React.ReactNode }) {
    const auth = await fetchAuthState();
    return (
        <Suspense fallback={<FullScreenLoader />}>
            <AuthDispatcher auth={auth}>{children}</AuthDispatcher>
        </Suspense>
    );
}
