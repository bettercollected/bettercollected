import { workspacesApi } from '@app/store/workspaces/api';

// A form's published versions for staff (backend: services/form_versions).
// Every call is `/workspaces/{id}/forms/{form}/...` and answers 422
// `form_revisions_disabled` while the server's FORM_REVISIONS_UI_ENABLED is off.

/** Who published a version: the member's current name; `former` once they have left. Never an id or an address. */
export interface VersionAuthor {
    name?: string | null;
    role?: string | null;
    former: boolean;
}

export interface FormVersionSummary {
    version: number;
    publishedAt?: string | null;
    publishedBy?: VersionAuthor | null;
    /** The newest published version: what respondents see now. */
    current: boolean;
}

export interface FormDraftState {
    /** What a restore sends back (`expectedUpdatedAt`). */
    updatedAt?: string | null;
    hasUnpublishedChanges: boolean;
}

export interface FormVersionList {
    versions: FormVersionSummary[];
    draft?: FormDraftState | null;
}

/** One coded change; the dashboard words it (utils/version-changes.ts). Values are form content, never answers. */
export interface VersionChange {
    kind: string;
    scope: 'form' | 'page' | 'question';
    ref?: string | null;
    title?: string | null;
    params: Record<string, any>;
}

export interface VersionCompare {
    fromVersion: string;
    toVersion: string;
    changed: boolean;
    entries: VersionChange[];
    truncated: boolean;
}

type FormKey = { workspaceId: string; formId: string };

const FORM_VERSIONS_TAG = 'FORM_VERSIONS_TAG';

export const formVersionsApi = workspacesApi.enhanceEndpoints({ addTagTypes: [FORM_VERSIONS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        getFormVersions: builder.query<FormVersionList, FormKey>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/versions`, method: 'GET' }),
            providesTags: [FORM_VERSIONS_TAG]
        }),
        // `from` and `to` are a version number or "draft".
        compareFormVersions: builder.query<VersionCompare, FormKey & { from: string; to: string }>({
            query: ({ workspaceId, formId, from, to }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/version-diff`, method: 'GET', params: { from, to } }),
            providesTags: [FORM_VERSIONS_TAG]
        }),
        // Replaces the draft's content with a version's; publishes nothing.
        restoreFormVersion: builder.mutation<{ restoredVersion: number; updatedAt?: string | null }, FormKey & { version: number; expectedUpdatedAt: string; replaceDraft: boolean }>({
            query: ({ workspaceId, formId, version, expectedUpdatedAt, replaceDraft }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/versions/${version}/restore`,
                method: 'POST',
                body: { expectedUpdatedAt, replaceDraft }
            }),
            invalidatesTags: [FORM_VERSIONS_TAG]
        })
    })
});

export const { useGetFormVersionsQuery, useCompareFormVersionsQuery, useRestoreFormVersionMutation } = formVersionsApi;
