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
    formId: string;
    status: PdfImportStatus;
    stage?: string | null;
    error?: string | null;
    fileName: string;
    contentType: string;
    sizeBytes: number;
    pageCount?: number | null;
    pages: PdfImportPage[];
    report: Record<string, any>;
    finishedStages?: string[];
    createdAt?: string;
    finishedAt?: string | null;
}

export interface ReviewBox {
    id: string;
    type: 'question' | 'staff_only';
    kind?: string | null;
    label: string;
    confidence?: number | null;
    bbox: [number, number, number, number];
}

export interface PdfImportReview {
    id: string;
    form_id: string;
    status: PdfImportStatus;
    pages: { number: number; width: number; height: number; route: string; has_image: boolean; boxes: ReviewBox[] }[];
    report: Record<string, any>;
}

export const pdfImportApi = createApi({
    reducerPath: PDF_IMPORT_REDUCER_PATH,
    baseQuery: fetchBaseQuery({ baseUrl: environments.API_ENDPOINT_HOST, credentials: 'include' }),
    tagTypes: ['PdfImport'],
    endpoints: (builder) => ({
        startPdfImport: builder.mutation<PdfImport, { workspaceId: string; file: File }>({
            query: ({ workspaceId, file }) => {
                const body = new FormData();
                body.append('file', file);
                return { url: `/workspaces/${workspaceId}/form-imports`, method: 'POST', body };
            }
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

export const { useStartPdfImportMutation, useGetPdfImportQuery, useGetPdfImportReviewQuery } = pdfImportApi;

export function pageImageUrl(workspaceId: string, importId: string, page: number) {
    return `${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/form-imports/${importId}/pages/${page}`;
}
