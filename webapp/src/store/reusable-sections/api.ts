import { workspacesApi } from '@app/store/workspaces/api';

/** A workspace's library of reusable sections (backend services/reusable_sections): groups of questions saved once and copied into forms. */
export const REUSABLE_SECTIONS_TAG = 'REUSABLE_SECTIONS_TAG';

export interface SectionSummary {
    id: string;
    name: string;
    description?: string | null;
    version: number;
    questionCount: number;
    updatedAt?: string;
}

/** What the server dropped or left out when a section was saved; `code` has a sentence in the builder's strings. */
export interface SectionWarning {
    code: string;
    fieldId?: string | null;
    title?: string | null;
}

export interface SectionDetail extends SectionSummary {
    /** The questions and containers in the builder's shape. */
    fields: Array<Record<string, any>>;
    containers: Array<Record<string, any>>;
    versions: number[];
    warnings: SectionWarning[];
}

/** What to put on a page: questions (marked, new ids) and the containers that group them. */
export interface SectionFragment {
    sectionId: string;
    version: number;
    instance: string;
    fields: Array<Record<string, any>>;
    containers: Array<Record<string, any>>;
}

export type ChangeStatus = 'added' | 'removed' | 'changed' | 'unchanged';

export interface SectionChange {
    key: string;
    id?: string | null;
    title?: string | null;
    status: ChangeStatus;
    /** title, type, required, options, logic, rules, settings */
    what: string[];
    modifiedInCopy: boolean;
}

export interface SectionPlan {
    sectionId: string;
    version: number;
    baseVersion?: number | null;
    baseKnown: boolean;
    instance: string;
    changes: SectionChange[];
    fields: Array<Record<string, any>>;
    containers: Array<Record<string, any>>;
    replaceIds: string[];
}

export const reusableSectionsApi = workspacesApi.enhanceEndpoints({ addTagTypes: [REUSABLE_SECTIONS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        getSections: builder.query<SectionSummary[], { workspaceId: string }>({
            query: ({ workspaceId }) => ({ url: `/workspaces/${workspaceId}/sections`, method: 'GET' }),
            providesTags: [REUSABLE_SECTIONS_TAG]
        }),
        getSection: builder.query<SectionDetail, { workspaceId: string; sectionId: string; version?: number }>({
            query: ({ workspaceId, sectionId, version }) => ({ url: `/workspaces/${workspaceId}/sections/${sectionId}`, method: 'GET', params: version ? { version } : undefined }),
            providesTags: [REUSABLE_SECTIONS_TAG]
        }),
        createSection: builder.mutation<SectionDetail, { workspaceId: string; name: string; description?: string; fields: Array<Record<string, any>>; containers?: Array<Record<string, any>> }>({
            query: ({ workspaceId, ...body }) => ({ url: `/workspaces/${workspaceId}/sections`, method: 'POST', body }),
            invalidatesTags: [REUSABLE_SECTIONS_TAG]
        }),
        saveSectionContent: builder.mutation<SectionDetail, { workspaceId: string; sectionId: string; fields: Array<Record<string, any>>; containers?: Array<Record<string, any>>; expectedVersion?: number }>({
            query: ({ workspaceId, sectionId, ...body }) => ({ url: `/workspaces/${workspaceId}/sections/${sectionId}/content`, method: 'PUT', body }),
            invalidatesTags: [REUSABLE_SECTIONS_TAG]
        }),
        updateSectionDetails: builder.mutation<SectionSummary, { workspaceId: string; sectionId: string; name?: string; description?: string | null }>({
            query: ({ workspaceId, sectionId, ...body }) => ({ url: `/workspaces/${workspaceId}/sections/${sectionId}`, method: 'PATCH', body }),
            invalidatesTags: [REUSABLE_SECTIONS_TAG]
        }),
        deleteSection: builder.mutation<null, { workspaceId: string; sectionId: string }>({
            query: ({ workspaceId, sectionId }) => ({ url: `/workspaces/${workspaceId}/sections/${sectionId}`, method: 'DELETE' }),
            invalidatesTags: [REUSABLE_SECTIONS_TAG]
        }),
        /** A copy of the section for a form: new ids, a marker on each question. */
        instantiateSection: builder.mutation<SectionFragment, { workspaceId: string; sectionId: string }>({
            query: ({ workspaceId, sectionId }) => ({ url: `/workspaces/${workspaceId}/sections/${sectionId}/instantiate`, method: 'POST' })
        }),
        /** The diff of a copy against the latest version, and the fragment that replaces it. */
        planSectionUpdate: builder.mutation<SectionPlan, { workspaceId: string; sectionId: string; instance: string; fields: Array<Record<string, any>> }>({
            query: ({ workspaceId, sectionId, ...body }) => ({ url: `/workspaces/${workspaceId}/sections/${sectionId}/update-plan`, method: 'POST', body })
        })
    })
});

export const { useGetSectionsQuery, useGetSectionQuery, useCreateSectionMutation, useSaveSectionContentMutation, useUpdateSectionDetailsMutation, useDeleteSectionMutation, useInstantiateSectionMutation, usePlanSectionUpdateMutation } = reusableSectionsApi;
