import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const OPEN_FORMULIEREN_IMPORT_REDUCER_PATH = 'openFormulierenImportApi';

/** What happened to an item of the source form (api contract section 5). */
export type ImportReportCode = 'dropped' | 'changed' | 'flagged' | 'ignored';

export interface ImportReportItem {
    code: ImportReportCode | string;
    kind: 'component' | 'logic' | 'variable' | 'feature' | 'setting' | 'archive' | string;
    key?: string | null;
    label?: string | null;
    /** Stable reason code: the sentences live in the webapp, keyed by it. */
    reason: string;
    severity?: 'warning' | 'info' | string;
    /** Only "national_identity_number" today. */
    flag?: string | null;
    /** 0-based page of the imported form. */
    step?: number | null;
    detail?: Record<string, string | number | boolean> | null;
}

export interface ImportSummary {
    pages: number;
    fields: number;
    logicRules: number;
    repeatingGroups?: number;
    dropped: number;
    flagged: number;
}

export interface OpenFormulierenImport {
    id: string;
    formId: string;
    status: string;
    needsReview: boolean;
    sourceKind?: string;
    sourceVersion?: string | null;
    fileName?: string | null;
    sizeBytes?: number | null;
    createdAt?: string;
    summary: ImportSummary;
    report: { truncated: boolean; items: ImportReportItem[] };
}

/** The body of a refusal: a stable `code`, an English `message`, and extra keys per code. */
export interface OpenFormulierenImportRefusal {
    code?: string;
    message?: string;
    maxBytes?: number;
    missing?: string[];
    file?: string;
    version?: string;
    supported?: string[];
    reportItems?: ImportReportItem[];
}

export const openFormulierenImportApi = createApi({
    reducerPath: OPEN_FORMULIEREN_IMPORT_REDUCER_PATH,
    baseQuery: fetchBaseQuery({ baseUrl: environments.API_ENDPOINT_HOST, credentials: 'include' }),
    tagTypes: ['OpenFormulierenImport'],
    endpoints: (builder) => ({
        uploadOpenFormulierenImport: builder.mutation<OpenFormulierenImport, { workspaceId: string; file: File }>({
            query: ({ workspaceId, file }) => {
                const body = new FormData();
                body.append('file', file);
                return { url: `/workspaces/${workspaceId}/open-formulieren-imports`, method: 'POST', body };
            },
            // The report screen opens straight from the upload's answer, without asking again.
            async onQueryStarted({ workspaceId }, { dispatch, queryFulfilled }) {
                try {
                    const { data } = await queryFulfilled;
                    dispatch(openFormulierenImportApi.util.upsertQueryData('getOpenFormulierenImport', { workspaceId, importId: data.id }, data));
                } catch {
                    // the dialog shows the refusal
                }
            }
        }),
        getOpenFormulierenImport: builder.query<OpenFormulierenImport, { workspaceId: string; importId: string }>({
            query: ({ workspaceId, importId }) => ({ url: `/workspaces/${workspaceId}/open-formulieren-imports/${encodeURIComponent(importId)}` }),
            providesTags: (_r, _e, arg) => [{ type: 'OpenFormulierenImport', id: arg.importId }]
        }),
        reviewOpenFormulierenImport: builder.mutation<OpenFormulierenImport, { workspaceId: string; importId: string; reviewed: boolean }>({
            query: ({ workspaceId, importId, reviewed }) => ({
                url: `/workspaces/${workspaceId}/open-formulieren-imports/${encodeURIComponent(importId)}/review`,
                method: 'POST',
                body: { reviewed }
            }),
            // the answer is the updated import: the report and the builder banner read it from the cache
            async onQueryStarted({ workspaceId, importId }, { dispatch, queryFulfilled }) {
                try {
                    const { data } = await queryFulfilled;
                    dispatch(openFormulierenImportApi.util.upsertQueryData('getOpenFormulierenImport', { workspaceId, importId }, data));
                } catch {
                    // the screen shows the failure
                }
            }
        })
    })
});

export const { useUploadOpenFormulierenImportMutation, useGetOpenFormulierenImportQuery, useReviewOpenFormulierenImportMutation } = openFormulierenImportApi;
