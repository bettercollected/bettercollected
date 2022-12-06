import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

import { AUTH_LOG_OUT, AUTH_TAG_TYPES } from './auth/types';
import customFetchBase from './customFetchBase';

// initialize an empty api service that we'll inject endpoints into later as needed

export const baseApi = createApi({
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST
        // credentials: 'include'
    }),
    tagTypes: [AUTH_TAG_TYPES, AUTH_LOG_OUT],
    // baseQuery: customFetchBase,
    endpoints: () => ({})
});
