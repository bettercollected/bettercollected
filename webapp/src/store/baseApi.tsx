import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

import customFetchBase from './customFetchBase';

// initialize an empty api service that we'll inject endpoints into later as needed

export const baseApi = createApi({
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST
        // credentials: 'include'
    }),
    // baseQuery: customFetchBase,
    endpoints: () => ({})
});
