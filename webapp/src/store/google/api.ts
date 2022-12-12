import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const GOOGLE_API = 'google';
export const GOOGLE_API_TAG = 'GOOGLE_API_TAG';

export const googleApiSlice = createApi({
    reducerPath: GOOGLE_API,
    tagTypes: [GOOGLE_API_TAG],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include',
        prepareHeaders: (headers, { getState }) => {
            headers.set('Access-Control-Allow-origin', 'http://localhost:8000');
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getForms: builder.query<any, null>({
            query: () => ({
                url: `forms/submissions`,
                method: 'GET',
                credentials: 'include'
            })
        }),
        importForms: builder.query<any, null>({
            query: () => ({
                url: 'forms/import',
                method: 'GET',
                credentials: 'include'
            })
        })
    })
});

export const { useGetFormsQuery, useImportFormsQuery } = googleApiSlice;
