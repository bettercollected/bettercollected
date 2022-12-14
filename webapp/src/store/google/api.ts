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
        getSubmissions: builder.query<any, null>({
            query: () => ({
                url: `forms/submissions`,
                method: 'GET',
                credentials: 'include'
            })
        }),
        getForms: builder.query<any, null>({
            query: () => ({
                url: 'forms/import',
                method: 'GET',
                credentials: 'include'
            })
        }),
        importForms: builder.mutation<any, null>({
            query: (body) => ({
                url: `workspaces/${environments.WORKSPACE_ID}/forms/import`,
                method: 'POST',
                body,
                credentials: 'include',
                prepareHeaders: (headers: any) => {
                    headers.set('Access-Control-Allow-origin', environments.API_ENDPOINT_HOST);
                    return headers;
                }
            })
        }),
        patchPinnedForm: builder.mutation<any, any>({
            query: (body) => ({
                url: `/workspaces/${environments.WORKSPACE_ID}/pin_forms`,
                method: 'PATCH',
                body,
                credentials: 'include',
                prepareHeaders: (headers: any) => {
                    headers.set('Access-Control-Allow-origin', environments.API_ENDPOINT_HOST);
                    return headers;
                }
            })
        }),
        getWorkspaceForms: builder.query<null, null>({
            query: () => ({
                url: `workspaces/${environments.WORKSPACE_ID}/forms?pinned=false`,
                method: 'GET',
                credentials: 'include'
            })
        })
    })
});

export const { useGetFormsQuery, useGetSubmissionsQuery, useImportFormsMutation, usePatchPinnedFormMutation, useGetWorkspaceFormsQuery } = googleApiSlice;
