import React, { Suspense } from 'react';

import AuthDispatcher from '@app/app/_dispatcher/AuthDispatcher';
import environments from '@app/configs/environments';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

async function fetchAuthState() {
    const res = await fetchWithCookies(
        environments.API_ENDPOINT_HOST + '/auth/status',
        { method: 'GET' }
    );
    return res;
}

export default async function AuthProvider({
    children
}: {
    children: React.ReactNode;
}) {
    const auth = await fetchAuthState();
    return (
        <Suspense fallback={<FullScreenLoader />}>
            <AuthDispatcher auth={auth}>{children}</AuthDispatcher>;
        </Suspense>
    );
}
