import { workspacesApi } from '@app/store/workspaces/api';
import type { WebhookVariable } from '@app/store/workspaces/webhooks-api';
import { ActionCondition, DeliveryStatus } from '@app/store/workspaces/webhooks-api';

// Email actions per form (docs/email-actions.md): mail to the form's team and a
// copy to the respondent. Every call is `/workspaces/{id}/forms/{form}/email-actions...`.

export interface EmailTemplate {
    subject: string;
    body: string;
}

export interface EmailActionField {
    source: string;
    key: string;
}

export interface EmailAction {
    id: string;
    name: string;
    enabled: boolean;
    en: EmailTemplate;
    nl: EmailTemplate;
    fields: EmailActionField[];
    teamRecipients: string[];
    respondentField?: string | null;
    condition?: ActionCondition | null;
    createdAt?: string | null;
    updatedAt?: string | null;
}

export interface EmailActionInput {
    name?: string;
    enabled?: boolean;
    en?: EmailTemplate;
    nl?: EmailTemplate;
    fields?: Array<{ source: string; key?: string | null }>;
    teamRecipients?: string[];
    /** null removes the copy; leaving it out keeps it */
    respondentField?: string | null;
    /** null removes the condition; leaving it out keeps it */
    condition?: ActionCondition | null;
}

export type EmailVariable = WebhookVariable;

export interface EmailActionsStatus {
    enabled: boolean;
    /** whether the instance has a mail server (MAIL_*) */
    configured: boolean;
}

/** Ids, codes and timings only: a delivery never names an address or carries content. */
export interface EmailDelivery {
    id: string;
    actionId: string;
    channel?: 'team' | 'respondent' | null;
    event: 'submission' | 'test' | string;
    responseId?: string | null;
    status: DeliveryStatus;
    attempts: number;
    lastErrorCode?: string | null;
    firstAttemptAt?: string | null;
    lastAttemptAt?: string | null;
    nextAttemptAt?: string | null;
    finishedAt?: string | null;
    createdAt?: string | null;
}

export interface EmailDeliveryPage {
    items: EmailDelivery[];
    total: number;
}

export interface EmailPreviewRequest {
    language: 'en' | 'nl';
    subject: string;
    body: string;
    fields: Array<{ source: string; key?: string | null }>;
}

export interface EmailPreview {
    subject: string;
    body: string;
}

type FormKey = { workspaceId: string; formId: string };

const ACTIONS_TAG = 'EMAIL_ACTIONS_TAG';
const DELIVERIES_TAG = 'EMAIL_DELIVERIES_TAG';

export const emailActionsApi = workspacesApi.enhanceEndpoints({ addTagTypes: [ACTIONS_TAG, DELIVERIES_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        // Any member may ask; enabled false hides every email screen.
        getEmailActionsStatus: builder.query<EmailActionsStatus, string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/email-actions/status`, method: 'GET' })
        }),
        getEmailActions: builder.query<EmailAction[], FormKey>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions`, method: 'GET' }),
            providesTags: [ACTIONS_TAG]
        }),
        getEmailVariables: builder.query<EmailVariable[], FormKey>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions/variables`, method: 'GET' })
        }),
        createEmailAction: builder.mutation<EmailAction, FormKey & { body: EmailActionInput }>({
            query: ({ workspaceId, formId, body }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions`, method: 'POST', body }),
            invalidatesTags: [ACTIONS_TAG]
        }),
        updateEmailAction: builder.mutation<EmailAction, FormKey & { actionId: string; body: EmailActionInput }>({
            query: ({ workspaceId, formId, actionId, body }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions/${actionId}`, method: 'PATCH', body }),
            invalidatesTags: [ACTIONS_TAG]
        }),
        deleteEmailAction: builder.mutation<void, FormKey & { actionId: string }>({
            query: ({ workspaceId, formId, actionId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions/${actionId}`, method: 'DELETE' }),
            invalidatesTags: [ACTIONS_TAG]
        }),
        // The template with made-up answers, rendered by the server's own renderer (nothing is sent).
        previewEmail: builder.mutation<EmailPreview, FormKey & { body: EmailPreviewRequest }>({
            query: ({ workspaceId, formId, body }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions/preview`, method: 'POST', body })
        }),
        // A mail with sample answers to the signed-in user only (429 after 5 a minute per action).
        sendEmailTest: builder.mutation<EmailDelivery, FormKey & { actionId: string; channel?: 'team' | 'respondent' }>({
            query: ({ workspaceId, formId, actionId, channel = 'team' }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/email-actions/${actionId}/test`, method: 'POST', body: { channel } }),
            invalidatesTags: [DELIVERIES_TAG]
        }),
        getEmailDeliveries: builder.query<EmailDeliveryPage, FormKey & { status?: DeliveryStatus[]; limit?: number; offset?: number }>({
            query: ({ workspaceId, formId, status = [], limit = 20, offset = 0 }) => {
                const params = new URLSearchParams();
                status.forEach((value) => params.append('status', value));
                params.set('limit', String(limit));
                params.set('offset', String(offset));
                return { url: `/workspaces/${workspaceId}/forms/${formId}/email-actions/deliveries?${params.toString()}`, method: 'GET' };
            },
            providesTags: [DELIVERIES_TAG]
        })
    })
});

export const {
    useGetEmailActionsStatusQuery,
    useGetEmailActionsQuery,
    useGetEmailVariablesQuery,
    useCreateEmailActionMutation,
    useUpdateEmailActionMutation,
    useDeleteEmailActionMutation,
    usePreviewEmailMutation,
    useSendEmailTestMutation,
    useGetEmailDeliveriesQuery
} = emailActionsApi;
