import { SUBMISSION_TAG, workspacesApi } from '@app/store/workspaces/api';

// Staff edit of a response's answers and its history (backend:
// services/response_revisions). Behind the server's RESPONSE_REVISIONS_ENABLED
// (422 `response_revisions_disabled` while it is off).

export interface RevisionActor {
    kind: 'staff' | 'respondent';
    name?: string | null;
    role?: string | null;
    former: boolean;
}

export interface RevisionEntry {
    seq: number;
    at?: string | null;
    actor: RevisionActor;
    changed: Array<{ id: string; title?: string | null }>;
}

export interface RevisionValues {
    seq: number;
    values: Record<string, Record<string, any> | null>;
}

type ResponseKey = { workspaceId: string; formId: string; responseId: string };

export const RESPONSE_REVISIONS_TAG = 'RESPONSE_REVISIONS_TAG';

export const responseRevisionsApi = workspacesApi.enhanceEndpoints({ addTagTypes: [RESPONSE_REVISIONS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        // `answers`: only the questions that changed, each as a respondent's answer.
        editResponseAnswers: builder.mutation<{ changed: string[]; revision?: number | null }, ResponseKey & { answers: Record<string, Record<string, any>> }>({
            query: ({ workspaceId, formId, responseId, answers }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/submissions/${encodeURIComponent(responseId)}/answers`,
                method: 'PATCH',
                body: { answers }
            }),
            invalidatesTags: [SUBMISSION_TAG, RESPONSE_REVISIONS_TAG]
        }),
        getResponseRevisions: builder.query<{ revisions: RevisionEntry[] }, ResponseKey>({
            query: ({ workspaceId, formId, responseId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/submissions/${encodeURIComponent(responseId)}/revisions`, method: 'GET' }),
            providesTags: [RESPONSE_REVISIONS_TAG]
        }),
        // One entry's previous values, on demand: never cached, so they leave the page when it does.
        getResponseRevisionValues: builder.query<RevisionValues, ResponseKey & { seq: number }>({
            query: ({ workspaceId, formId, responseId, seq }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/submissions/${encodeURIComponent(responseId)}/revisions/${seq}`, method: 'GET' }),
            keepUnusedDataFor: 0
        })
    })
});

export const { useEditResponseAnswersMutation, useGetResponseRevisionsQuery, useLazyGetResponseRevisionValuesQuery } = responseRevisionsApi;
