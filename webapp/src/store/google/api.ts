import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { StandardFormDto } from '@app/models/dtos/form';
import { IGenericAPIResponse } from '@app/models/dtos/genericResponse';
import { GoogleMinifiedFormDto } from '@app/models/dtos/googleForm';

export const GOOGLE_API = 'google';
export const GOOGLE_API_TAG = 'GOOGLE_API_TAG';
export const GET_GOOGLE_FORMS = 'GET_GOOGLE_FORMS';

export const googleApiSlice = createApi({
    reducerPath: GOOGLE_API,
    tagTypes: [GOOGLE_API_TAG, GET_GOOGLE_FORMS],
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include',
        prepareHeaders: (headers, { getState }) => {
            headers.set('Access-Control-Allow-origin', environments.API_ENDPOINT_HOST);
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getSubmissions: builder.query<any, void>({
            query: () => ({
                url: `workspaces/${environments.WORKSPACE_ID}/allSubmissions`,
                method: 'GET',
                credentials: 'include'
            })
        }),
        getMinifiedForms: builder.query<IGenericAPIResponse<Array<GoogleMinifiedFormDto>>, void>({
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
            }),
            invalidatesTags: [GET_GOOGLE_FORMS]
        }),
        patchPinnedForm: builder.mutation<any, any>({
            query: (body) => ({
                url: `/workspaces/${environments.WORKSPACE_ID}/pin_forms`,
                method: 'PATCH',
                body,
                credentials: 'include'
            })
        }),
        getWorkspaceForms: builder.query<IGenericAPIResponse<Array<StandardFormDto>>, void>({
            query: () => ({
                url: `workspaces/${environments.WORKSPACE_ID}/forms`,
                method: 'GET',
                credentials: 'include'
            }),
            providesTags: [GET_GOOGLE_FORMS]
        })
    })
});

export const { useGetMinifiedFormsQuery, useGetSubmissionsQuery, useImportFormsMutation, usePatchPinnedFormMutation, useGetWorkspaceFormsQuery } = googleApiSlice;
