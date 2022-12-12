import { BaseQueryFn, FetchArgs, FetchBaseQueryError, fetchBaseQuery } from '@reduxjs/toolkit/query';
import { Mutex } from 'async-mutex';

import environments from '@app/configs/environments';

// Create a new mutex
const mutex = new Mutex();

const baseQuery = fetchBaseQuery({
    baseUrl: environments.API_ENDPOINT_HOST
});

const customFetchBase: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (args, api, extraOptions) => {
    // wait until the mutex is available without locking it
    await mutex.waitForUnlock();
    let result = await baseQuery(
        {
            url: '/auth/refresh_token',
            method: 'POST',
            credentials: 'include'
        },
        api,
        extraOptions
    );

    if ((result.error?.data as any)?.message === 'You are not logged in') {
        if (!mutex.isLocked()) {
            const release = await mutex.acquire();

            try {
                const refreshResult = await baseQuery({ credentials: 'include', url: 'auth/refresh_token' }, api, extraOptions);
                console.log('refresh: ', refreshResult);

                // console.log('inside custom base');

                if (refreshResult.data) {
                    console.log('login');
                    // Retry the initial query
                    result = await baseQuery(args, api, extraOptions);
                } else {
                    console.log('logout');

                    // api.dispatch(logout());
                    // window.location.href = '/login';
                }
            } finally {
                // release must be called once the mutex should be released again.
                release();
            }
        } else {
            // wait until the mutex is available without locking it
            await mutex.waitForUnlock();
            result = await baseQuery(args, api, extraOptions);
        }
    }

    return result;
};

export default customFetchBase;
