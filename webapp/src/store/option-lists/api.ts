import { workspacesApi } from '@app/store/workspaces/api';
import type { OptionSource, SourceOption } from '@app/utils/option-sources';

/** A workspace's option lists (backend services/option_lists): reference data a choice question can take its options from. */
export const OPTION_LISTS_TAG = 'OPTION_LISTS_TAG';

export interface OptionListItem {
    id?: string;
    label: string;
    group?: string | null;
}

export interface OptionListSummary {
    id: string;
    name: string;
    order: 'manual' | 'alphabetical';
    itemCount: number;
    revision: number;
    formsUsing: number;
    updatedAt?: string;
}

export interface OptionListDetail extends OptionListSummary {
    items: OptionListItem[];
    totalItems: number;
    usedBy: Array<{ formId: string; title?: string | null }>;
}

export interface SourcePreview {
    items: SourceOption[];
    total: number;
    /** All the options of the source, before the search and the parent's filter. */
    options: number;
    /** The responses behind another form's answers (a count, never a value). */
    responses: number;
    truncated: boolean;
    available: boolean;
}

export const optionListsApi = workspacesApi.enhanceEndpoints({ addTagTypes: [OPTION_LISTS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        getOptionLists: builder.query<OptionListSummary[], { workspaceId: string }>({
            query: ({ workspaceId }) => ({ url: `/workspaces/${workspaceId}/option-lists`, method: 'GET' }),
            providesTags: [OPTION_LISTS_TAG]
        }),
        getOptionList: builder.query<OptionListDetail, { workspaceId: string; listId: string; limit?: number; offset?: number }>({
            query: ({ workspaceId, listId, limit = 2000, offset = 0 }) => ({ url: `/workspaces/${workspaceId}/option-lists/${listId}`, method: 'GET', params: { limit, offset } }),
            providesTags: [OPTION_LISTS_TAG]
        }),
        createOptionList: builder.mutation<OptionListDetail, { workspaceId: string; name: string; order?: 'manual' | 'alphabetical'; items?: OptionListItem[] }>({
            query: ({ workspaceId, ...body }) => ({ url: `/workspaces/${workspaceId}/option-lists`, method: 'POST', body }),
            invalidatesTags: [OPTION_LISTS_TAG]
        }),
        updateOptionList: builder.mutation<OptionListDetail, { workspaceId: string; listId: string; name?: string; order?: 'manual' | 'alphabetical'; items?: OptionListItem[]; expectedRevision?: number }>({
            query: ({ workspaceId, listId, ...body }) => ({ url: `/workspaces/${workspaceId}/option-lists/${listId}`, method: 'PATCH', body }),
            invalidatesTags: [OPTION_LISTS_TAG]
        }),
        deleteOptionList: builder.mutation<null, { workspaceId: string; listId: string }>({
            query: ({ workspaceId, listId }) => ({ url: `/workspaces/${workspaceId}/option-lists/${listId}`, method: 'DELETE' }),
            invalidatesTags: [OPTION_LISTS_TAG]
        }),
        importOptionListCsv: builder.mutation<OptionListDetail, { workspaceId: string; listId: string; csv: string; expectedRevision?: number }>({
            query: ({ workspaceId, listId, csv, expectedRevision }) => ({
                url: `/workspaces/${workspaceId}/option-lists/${listId}/import`,
                method: 'POST',
                params: expectedRevision ? { expectedRevision } : undefined,
                body: csv,
                headers: { 'Content-Type': 'text/csv' }
            }),
            invalidatesTags: [OPTION_LISTS_TAG]
        }),
        exportOptionListCsv: builder.mutation<string, { workspaceId: string; listId: string }>({
            query: ({ workspaceId, listId }) => ({ url: `/workspaces/${workspaceId}/option-lists/${listId}/export`, method: 'GET', responseHandler: (response) => response.text() })
        }),
        /** What a source offers now, for the builder (needs form.edit; another form's answers also response.read on that form). */
        previewOptionSource: builder.mutation<SourcePreview, { workspaceId: string; source: OptionSource; formId?: string; parentLabels?: string[]; q?: string; limit?: number; offset?: number }>({
            query: ({ workspaceId, ...body }) => ({ url: `/workspaces/${workspaceId}/option-sources/preview`, method: 'POST', body })
        })
    })
});

export const { useGetOptionListsQuery, useGetOptionListQuery, useCreateOptionListMutation, useUpdateOptionListMutation, useDeleteOptionListMutation, useImportOptionListCsvMutation, useExportOptionListCsvMutation, usePreviewOptionSourceMutation } =
    optionListsApi;
