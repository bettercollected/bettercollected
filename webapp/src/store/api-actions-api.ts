import { createApi } from '@reduxjs/toolkit/dist/query/react';
import { fetchBaseQuery } from '@reduxjs/toolkit/query';

import environments from '@app/configs/environments';

export const apiActionsApi = createApi({
    reducerPath: 'api-actions',
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    keepUnusedDataFor: 0,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getAllIntegrations: builder.query<any, any>({
            query: (request?: any) => ({
                url: `/actions`,
                method: 'GET',
                params: {
                    workspace_id: request?.workspaceId
                }
            })
        }),
        getSingleIntegration: builder.query<any, any>({
            query: (request) => ({
                url: `/actions/${request.actionId}`,
                method: 'GET'
            })
        }),
        addActionToForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/actions`,
                method: 'PATCH',
                body: request.body
            })
        }),
        removeActionFromForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/actions/${request.actionId}`,
                method: 'DELETE'
            })
        })
    })
});

export const { useGetAllIntegrationsQuery, useGetSingleIntegrationQuery, useAddActionToFormMutation, useRemoveActionFromFormMutation } = apiActionsApi;
