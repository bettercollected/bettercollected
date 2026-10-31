import type { LogicCondition, LogicalOperator } from '@app/models/types/form-builder-shared';
import { workspacesApi } from '@app/store/workspaces/api';

/**
 * When an action (a webhook or an email action) runs: the form's logic
 * conditions, evaluated by the server on the submitted answers. No condition,
 * or null: every submission.
 */
export interface ActionCondition {
    operator: LogicalOperator | 'AND' | 'OR';
    conditions: LogicCondition[];
}

// Sending a form's submissions to an https address of the workspace's own
// (docs/webhooks.md). Every call is `/workspaces/{id}/forms/{form}/webhooks...`.
// The signing secret comes back once, from create and rotate; no other
// response carries one, only `hasSecret`.

export interface WebhookField {
    source: string;
    key: string;
}

/** What the list shows: the host, never the address (it can hold a token). */
export interface Webhook {
    id: string;
    host: string;
    enabled: boolean;
    fields: WebhookField[];
    condition?: ActionCondition | null;
    hasSecret: boolean;
    secretSetAt?: string | null;
    createdAt?: string | null;
    updatedAt?: string | null;
}

/** The owner-facing view of one webhook: the only read that carries the address, to edit it. */
export interface WebhookDetail extends Webhook {
    url: string;
}

/** The answer of create and rotate: the only place the secret is. */
export interface WebhookWithSecret extends Webhook {
    secret: string;
}

export interface WebhookInput {
    url?: string;
    fields?: Array<{ source: string; key?: string | null }>;
    enabled?: boolean;
    /** null removes the condition; leaving it out keeps it */
    condition?: ActionCondition | null;
}

export interface WebhookVariable {
    source: string;
    label: string;
    type: string;
    supported: boolean;
    /** Why a question is greyed out: `file_not_sent`, `type_not_supported`, ... */
    reason?: string | null;
}

export type DeliveryStatus = 'pending' | 'in_progress' | 'retrying' | 'delivered' | 'failed' | 'cancelled';

/** Ids, codes and timings only: a delivery never carries answer content. */
export interface WebhookDelivery {
    id: string;
    actionType: string;
    webhookId: string;
    host?: string | null;
    event: 'submission' | 'test' | string;
    responseId?: string | null;
    status: DeliveryStatus;
    attempts: number;
    lastErrorCode?: string | null;
    lastHttpStatus?: number | null;
    lastDurationMs?: number | null;
    firstAttemptAt?: string | null;
    lastAttemptAt?: string | null;
    nextAttemptAt?: string | null;
    finishedAt?: string | null;
    createdAt?: string | null;
}

export interface WebhookDeliveryPage {
    items: WebhookDelivery[];
    total: number;
}

export interface WebhookAuditEntry {
    id: string;
    webhookId: string;
    event: string;
    actorId?: string | null;
    changed: string[];
    host?: string | null;
    createdAt?: string | null;
}

export interface WebhookDeliveriesQuery {
    workspaceId: string;
    formId: string;
    status?: DeliveryStatus[];
    limit?: number;
    offset?: number;
}

type FormKey = { workspaceId: string; formId: string };

const WEBHOOKS_TAG = 'WEBHOOKS_TAG';
const DELIVERIES_TAG = 'WEBHOOK_DELIVERIES_TAG';
const AUDIT_TAG = 'WEBHOOK_AUDIT_TAG';

export const webhooksApi = workspacesApi.enhanceEndpoints({ addTagTypes: [WEBHOOKS_TAG, DELIVERIES_TAG, AUDIT_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        // Any member may ask; false hides every webhook screen.
        getWebhooksStatus: builder.query<{ enabled: boolean }, string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/webhooks/status`, method: 'GET' })
        }),
        getWebhooks: builder.query<Webhook[], FormKey>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks`, method: 'GET' }),
            providesTags: [WEBHOOKS_TAG]
        }),
        getWebhookDetail: builder.query<WebhookDetail, FormKey & { webhookId: string }>({
            query: ({ workspaceId, formId, webhookId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/${webhookId}/detail`, method: 'GET' }),
            providesTags: [WEBHOOKS_TAG]
        }),
        getWebhookVariables: builder.query<WebhookVariable[], FormKey>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/variables`, method: 'GET' })
        }),
        createWebhook: builder.mutation<WebhookWithSecret, FormKey & { body: WebhookInput }>({
            query: ({ workspaceId, formId, body }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks`, method: 'POST', body }),
            invalidatesTags: [WEBHOOKS_TAG, AUDIT_TAG]
        }),
        updateWebhook: builder.mutation<Webhook, FormKey & { webhookId: string; body: WebhookInput }>({
            query: ({ workspaceId, formId, webhookId, body }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/${webhookId}`, method: 'PATCH', body }),
            invalidatesTags: [WEBHOOKS_TAG, AUDIT_TAG]
        }),
        deleteWebhook: builder.mutation<void, FormKey & { webhookId: string }>({
            query: ({ workspaceId, formId, webhookId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/${webhookId}`, method: 'DELETE' }),
            invalidatesTags: [WEBHOOKS_TAG, AUDIT_TAG]
        }),
        rotateWebhookSecret: builder.mutation<WebhookWithSecret, FormKey & { webhookId: string }>({
            query: ({ workspaceId, formId, webhookId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/${webhookId}/rotate-secret`, method: 'POST' }),
            invalidatesTags: [WEBHOOKS_TAG, AUDIT_TAG]
        }),
        // A real, signed delivery of sample data (owners and admins; 429 after 5 a minute).
        sendWebhookTest: builder.mutation<WebhookDelivery, FormKey & { webhookId: string }>({
            query: ({ workspaceId, formId, webhookId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/${webhookId}/test`, method: 'POST' }),
            invalidatesTags: [DELIVERIES_TAG]
        }),
        getWebhookDeliveries: builder.query<WebhookDeliveryPage, WebhookDeliveriesQuery>({
            query: ({ workspaceId, formId, status = [], limit = 20, offset = 0 }) => {
                const params = new URLSearchParams();
                status.forEach((value) => params.append('status', value));
                params.set('limit', String(limit));
                params.set('offset', String(offset));
                return { url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/deliveries?${params.toString()}`, method: 'GET' };
            },
            providesTags: [DELIVERIES_TAG]
        }),
        getWebhookAudit: builder.query<WebhookAuditEntry[], FormKey>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/webhooks/audit`, method: 'GET' }),
            providesTags: [AUDIT_TAG]
        })
    })
});

export const {
    useGetWebhooksStatusQuery,
    useGetWebhooksQuery,
    useGetWebhookDetailQuery,
    useGetWebhookVariablesQuery,
    useCreateWebhookMutation,
    useUpdateWebhookMutation,
    useDeleteWebhookMutation,
    useRotateWebhookSecretMutation,
    useSendWebhookTestMutation,
    useGetWebhookDeliveriesQuery,
    useGetWebhookAuditQuery
} = webhooksApi;
