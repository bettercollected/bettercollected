import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const PDF_IMPORT_REDUCER_PATH = 'pdfImportApi';

export type PdfImportStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface PdfImportPage {
    number: number;
    width: number;
    height: number;
    route: 'widgets' | 'text' | 'vision' | 'scan' | string;
    reasons?: string[];
}

export interface PdfImport {
    id: string;
    /** null once a failed import has removed its empty draft form. */
    formId: string | null;
    status: PdfImportStatus;
    stage?: string | null;
    error?: string | null;
    /** Stable reason for `error` (a refusal code, "no_questions", "unavailable", "interrupted", "failed", or "waiting_for_reader" while queued); the screens translate it. */
    errorCode?: string | null;
    fileName: string;
    contentType: string;
    sizeBytes: number;
    pageCount?: number | null;
    pages: PdfImportPage[];
    report: Record<string, any>;
    finishedStages?: string[];
    /** The uploader agreed to send this document to the AI provider. */
    aiConsent?: boolean;
    createdAt?: string;
    finishedAt?: string | null;
}

export interface ReviewBox {
    id: string;
    type: 'question' | 'staff_only';
    kind?: string | null;
    label: string;
    confidence?: number | null;
    /** false: the wording was written by the AI, not found on the page. */
    grounded?: boolean;
    bbox: [number, number, number, number];
}

export interface PdfImportReview {
    id: string;
    form_id: string;
    status: PdfImportStatus;
    pages: { number: number; width: number; height: number; route: string; has_image: boolean; boxes: ReviewBox[] }[];
    report: Record<string, any>;
}

export interface PdfImportAi {
    /** Public name of the provider an import with consent would use. */
    provider: string;
    /** Whether this server has that provider configured. */
    available: boolean;
    /** Whether the workspace has opted in to AI (#715); required on top of the per-upload consent. */
    enabled?: boolean;
}

export const pdfImportApi = createApi({
    reducerPath: PDF_IMPORT_REDUCER_PATH,
    baseQuery: fetchBaseQuery({ baseUrl: environments.API_ENDPOINT_HOST, credentials: 'include' }),
    tagTypes: ['PdfImport'],
    endpoints: (builder) => ({
        startPdfImport: builder.mutation<PdfImport, { workspaceId: string; file: File; aiConsent: boolean }>({
            query: ({ workspaceId, file, aiConsent }) => {
                const body = new FormData();
                body.append('file', file);
                // consent is only ever sent when the user ticked the box
                if (aiConsent === true) body.append('ai_consent', 'true');
                return { url: `/workspaces/${workspaceId}/form-imports`, method: 'POST', body };
            }
        }),
        getPdfImportAi: builder.query<PdfImportAi, { workspaceId: string }>({
            query: ({ workspaceId }) => ({ url: `/workspaces/${workspaceId}/form-imports/ai` })
        }),
        getPdfImport: builder.query<PdfImport, { workspaceId: string; importId: string }>({
            query: ({ workspaceId, importId }) => ({ url: `/workspaces/${workspaceId}/form-imports/${importId}` }),
            providesTags: (_r, _e, arg) => [{ type: 'PdfImport', id: arg.importId }]
        }),
        getPdfImportReview: builder.query<PdfImportReview, { workspaceId: string; importId: string }>({
            query: ({ workspaceId, importId }) => ({ url: `/workspaces/${workspaceId}/form-imports/${importId}/review` })
        })
    })
});

export const { useStartPdfImportMutation, useGetPdfImportAiQuery, useGetPdfImportQuery, useGetPdfImportReviewQuery } = pdfImportApi;

export function pageImageUrl(workspaceId: string, importId: string, page: number) {
    return `${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/form-imports/${importId}/pages/${page}`;
}
