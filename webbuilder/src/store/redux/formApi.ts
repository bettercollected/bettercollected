import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const formsApi = createApi({
    reducerPath: 'formsApi',
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set(
                'Access-Control-Allow-Origin',
                environments.API_ENDPOINT_HOST || ''
            );
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        createV2Form: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms`,
                method: 'POST',
                body: request.body
            })
        }),
        patchV2Form: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}`,
                method: 'PATCH',
                body: request.body
            })
        })
    })
});

export const { useCreateV2FormMutation, usePatchV2FormMutation } = formsApi;
