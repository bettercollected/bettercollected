import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/dist/query/react';

import environments from '@app/configs/environments';

import { AUTH_TAG_TYPES } from './types';

// export const authApi = baseApi.injectEndpoints({
//     endpoints: (builder) => ({
//         getLogout: builder.query<any, void>({
//             query: () => ({
//                 url: `/auth/logout`,
//                 method: 'GET',
//                 credentials: 'include'
//             }),
//             providesTags: [AUTH_LOG_OUT]
//         }),
//         getStatus: builder.query<any, any>({
//             query: (path) => ({
//                 url: `/auth/${path}`,
//                 method: 'GET',
//                 credentials: 'include'
//             }),
//             providesTags: (_) => [AUTH_TAG_TYPES]
//         })
//     })
// });

export const authApi = createApi({
    tagTypes: [AUTH_TAG_TYPES],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include',
        prepareHeaders: (headers, { getState }) => {
            headers.set('Access-Control-Allow-origin', environments.API_ENDPOINT_HOST);
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getLogout: builder.query<any, void>({
            query: () => ({
                url: `/auth/logout`,
                method: 'GET',
                credentials: 'include'
            })
            // providesTags: [AUTH_TAG_TYPES]
        }),
        getStatus: builder.query<any, any>({
            query: (path) => ({
                url: `/auth/${path}`,
                method: 'GET',
                credentials: 'include'
            })
        })
    })
});

export const { useGetLogoutQuery, useLazyGetLogoutQuery, useGetStatusQuery } = authApi;
