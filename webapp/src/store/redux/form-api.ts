import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { FormOutline } from '@app/utils/ai-outline';

export interface BuildFromOutlineResponse {
    formId: string;
    title: string;
    quality: { score: number; passed: boolean; findings: { code: string; severity: string; message: string; where: string[] }[] };
    notes: string[];
}

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
        // The organisation logo (utils/form-logo.ts): PNG, JPEG or WebP, at most 1 MB.
        uploadFormLogo: builder.mutation<any, { workspaceId: string; formId: string; file: File }>({
            query: ({ workspaceId, formId, file }) => {
                const body = new FormData();
                body.append('file', file);
                return { url: `/workspaces/${workspaceId}/forms/${formId}/logo`, method: 'PUT', body };
            }
        }),
        removeFormLogo: builder.mutation<any, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/logo`,
                method: 'DELETE'
            })
        }),
        publishV2Form: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/publish`,
                method: 'POST',
                body: request.body
            })
        }),
        // The form's live (latest published) version, as staff read it: its theme tells whether an older form's
        // colours changed since it went live (utils/publish-checks.ts themeContrastGate). 404 while it was never published.
        getPublishedForm: builder.query<any, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ method: 'GET', url: `/workspaces/${workspaceId}/forms/${formId}`, params: { published: true } }),
            keepUnusedDataFor: 0
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
        createFormWithAI: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/ai`,
                method: 'POST',
                body: request.body
            })
        }),
        // Outline-first AI creation: the outline to review, then the build.
        outlineFormWithAI: builder.mutation<{ outline: FormOutline }, { workspaceId: string; body: { prompt: string; documentText?: string } }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/ai/outline`,
                method: 'POST',
                body: request.body
            })
        }),
        buildFormFromOutline: builder.mutation<BuildFromOutlineResponse, { workspaceId: string; body: { outline: FormOutline; fillGaps?: boolean } }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/ai/build`,
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
        }),
        acceptAIProposal: builder.mutation<any, { workspaceId: string; formId: string; proposalId: string; opIndexes?: number[] }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/proposals/${encodeURIComponent(request.proposalId)}/accept`,
                method: 'POST',
                body: request.opIndexes ? { opIndexes: request.opIndexes } : {}
            })
        }),
        rejectAIProposal: builder.mutation<any, { workspaceId: string; formId: string; proposalId: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/proposals/${encodeURIComponent(request.proposalId)}/reject`,
                method: 'POST'
            })
        }),
        getAIInsights: builder.query<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/insights`,
                method: 'GET'
            })
        }),
        updateAIInsightsSettings: builder.mutation<any, { workspaceId: string; formId: string; enabled: boolean }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/insights/settings`,
                method: 'PUT',
                body: { enabled: request.enabled }
            })
        }),
        generateAIInsights: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/ai/insights`,
                method: 'POST',
                body: {}
            })
        })
    })
});

export const {
    useCreateV2FormMutation,
    usePatchV2FormMutation,
    useUploadFormLogoMutation,
    useRemoveFormLogoMutation,
    usePublishV2FormMutation,
    useGetFormResponseQuery,
    useLazyGetPublishedFormQuery,
    useSubmitResponseMutation,
    useSendFlowEventMutation,
    useGetFlowAnalyticsQuery,
    useLazyLogOutQuery,
    useCreateFormWithAIMutation,
    useOutlineFormWithAIMutation,
    useBuildFormFromOutlineMutation,
    useChatEditFormWithAIMutation,
    useReviewFormWithAIMutation,
    useApplyAIReviewFixMutation,
    useAcceptAIProposalMutation,
    useRejectAIProposalMutation,
    useGetAIInsightsQuery,
    useGenerateAIInsightsMutation,
    useUpdateAIInsightsSettingsMutation
} = formsApi;
