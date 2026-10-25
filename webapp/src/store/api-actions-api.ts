import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { Action } from '@app/models/dtos/actions';

export const apiActionsApi = createApi({
    reducerPath: 'api-actions',
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    keepUnusedDataFor: 0,
    tagTypes: ['ActionReconsent'],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getAllIntegrations: builder.query<Array<Action>, any>({
            query: (request?: any) => ({
                url: `/actions`,
                method: 'GET',
                params: {
                    workspace_id: request?.workspaceId
                }
            })
        }),
        getSingleIntegration: builder.query<Action, any>({
            query: (request) => ({
                url: `/actions/${request.actionId}`,
                method: 'GET'
            })
        }),
        addActionToForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/actions`,
                method: 'POST',
                body: request.body
            }),
            // Adding the Sheets action again after a reconnect stores the new
            // grant's sheet: ask the reconnect status again.
            invalidatesTags: ['ActionReconsent']
        }),
        // Whether a Google Sheets action on the form still holds a grant from
        // before the `drive.file` flow and must be reconnected (needs form.edit).
        getActionReconsentStatus: builder.query<{ needs_reconsent: boolean }, { workspaceId: string; formId: string; actionId: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/actions/${request.actionId}/reconsent`,
                method: 'GET'
            }),
            providesTags: ['ActionReconsent']
        }),
        removeActionFromForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/actions/${request.actionId}`,
                method: 'DELETE'
            })
        }),
        updateActionStatusInForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/actions`,
                method: 'PATCH',
                body: request.body
            })
        })
    })
});

export const { useGetAllIntegrationsQuery, useGetSingleIntegrationQuery, useAddActionToFormMutation, useRemoveActionFromFormMutation, useUpdateActionStatusInFormMutation, useGetActionReconsentStatusQuery } = apiActionsApi;
