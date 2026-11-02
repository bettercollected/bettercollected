import { workspacesApi } from '@app/store/workspaces/api';

// Embedding a workspace's forms in other sites (backend services/form_embed.py, docs/embed.md): the sites
// allowed to show its forms in a frame. Every call is `/workspaces/{id}/embed/settings`. The server answers
// 404 while FORM_EMBED_ENABLED is off.

export interface EmbedSettings {
    /** Canonical origins, e.g. `https://www.example.org` or `https://*.example.org`. */
    origins: string[];
    /** Whether the caller may change them (workspace admins). */
    canManage: boolean;
    maxOrigins: number;
}

/** The public policy of a workspace: whether this server has embedding on, and the sites it allows. */
export interface EmbedPolicy {
    enabled: boolean;
    origins: string[];
}

const EMBED_SETTINGS_TAG = 'EMBED_SETTINGS_TAG';

export const embedApi = workspacesApi.enhanceEndpoints({ addTagTypes: [EMBED_SETTINGS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        // Public (no sign-in): the respondent page asks it to know whether it may tell the page around it anything.
        getEmbedPolicy: builder.query<EmbedPolicy, string>({
            query: (workspaceId) => ({ url: `/workspaces/embed/policy?workspace_id=${encodeURIComponent(workspaceId)}`, method: 'GET' })
        }),
        getEmbedSettings: builder.query<EmbedSettings, string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/embed/settings`, method: 'GET' }),
            providesTags: [EMBED_SETTINGS_TAG]
        }),
        // Replaces the whole list; a refusal names the entry (`index`) and why (`code`).
        updateEmbedSettings: builder.mutation<EmbedSettings, { workspaceId: string; origins: string[] }>({
            query: ({ workspaceId, origins }) => ({ url: `/workspaces/${workspaceId}/embed/settings`, method: 'PUT', body: { origins } }),
            invalidatesTags: [EMBED_SETTINGS_TAG]
        })
    })
});

export const { useGetEmbedPolicyQuery, useGetEmbedSettingsQuery, useUpdateEmbedSettingsMutation } = embedApi;
