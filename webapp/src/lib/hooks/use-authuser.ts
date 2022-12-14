import { useEffect, useMemo } from 'react';

import Router from 'next/router';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { authApi, useGetStatusQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

export default function useUser({ redirectTo = '', redirectIfFound = false } = {}) {
    //TODO: get the user authentication from the endpoint
    // this provides us with the user
    const { isLoading, refetch, isError, isSuccess } = useGetStatusQuery('status');

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const user = useAppSelector(statusQuerySelect);

    useEffect(() => {
        // if no direction is needed, just return
        // if the user is returned, we need not redirect
        const userPresent = user?.data?.payload?.content?.user;

        if (userPresent !== undefined && isSuccess && !isLoading) {
            return;
        } else if (!isLoading && userPresent !== undefined) {
            Router.push('/');
        } else if (isError) {
            Router.push('/');
        }
        // if the user is not logged in,
        // we'll need to redirect to the landing page
    }, [user, redirectIfFound, redirectTo]);

    return { user, isLoading };
}
