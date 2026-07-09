import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const formsApi = createApi({
    reducerPath: 'formsApi',
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST || '');
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
        }),
        publishV2Form: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/publish`,
                method: 'POST',
                body: request.body
            })
        }),
        getFormResponse: builder.query<any, any>({
            query: (request) => ({
                method: 'GET',
                url: `/workspaces/${request.workspaceId}/submissions/${request.responseId}`
            })
        }),
        submitResponse: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/response`,
                method: 'POST',
                body: request.body
            })
        }),
        // One anonymous navigation step for drop-off analytics (no answers, no identity).
        sendFlowEvent: builder.mutation<any, { workspaceId: string; formId: string; sessionId: string; fromPage: string; toPage: string }>({
            query: ({ workspaceId, formId, sessionId, fromPage, toPage }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/flow-events`,
                method: 'POST',
                body: { sessionId, fromPage, toPage }
            })
        }),
        getFlowAnalytics: builder.query<{ totalSessions: number; submittedSessions: number; dropOffs: Record<string, number>; transitions: Array<{ from: string; to: string; count: number }> }, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/flow-analytics`,
                method: 'GET'
            })
        }),
        logOut: builder.query<any, any>({
            query: () => ({
                url: `/auth/logout`,
                method: 'GET'
            })
        }),
        chatEditFormWithAI: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/chat`,
                method: 'POST',
                body: request.body
            })
        }),
        createFormWithAI: builder.mutation<any,any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/ai`,
                method: 'POST',
                body: request.body
            })
        }),
        reviewFormWithAI: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/review`,
                method: 'POST',
                body: request.body ?? {}
            })
        }),
        applyAIReviewFix: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/review/apply`,
                method: 'POST',
                body: request.body
            })
        })
    })
});

export const { useCreateV2FormMutation, usePatchV2FormMutation, usePublishV2FormMutation, useGetFormResponseQuery, useSubmitResponseMutation, useSendFlowEventMutation, useGetFlowAnalyticsQuery, useLazyLogOutQuery, useCreateFormWithAIMutation, useChatEditFormWithAIMutation, useReviewFormWithAIMutation, useApplyAIReviewFixMutation } = formsApi;
