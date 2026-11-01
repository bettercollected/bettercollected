import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import type { WorkspaceSelection } from '@app/lib/workspace-selection';
import { AnswerDto, InternalAnswerMeta, StaffFeedback, StandardFormDto, StandardFormResponseDto, WorkspaceResponderDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { Page } from '@app/models/dtos/page';
import { WorkspaceDomainDto } from '@app/models/dtos/workspace-domain-dto';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { CreateScimDirectoryRequest, ScimCredentialsDto, ScimDirectoryDto, ScimGroupDto, ScimOverviewDto, ScimResyncDto } from '@app/models/dtos/workspace-scim-dto';
import { CreateSsoConnectionRequest, SsoAuditPageDto, SsoConnectionDto, SsoOverviewDto, SsoSettingsDto, UpdateSsoSettingsRequest } from '@app/models/dtos/workspace-sso-dto';
import { WorkspaceStatsDto } from '@app/models/dtos/workspace-stats-dto';
import { DeclineReason, DeletionRequestOutcome } from '@app/models/enums/deletion-request';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { IGetAllSubmissionsQuery, IGetFormSubmissionsQuery, IGetWorkspaceFormQuery, IGetWorkspaceSubmissionQuery, IPatchFormSettingsRequest, ISearchWorkspaceFormsQuery } from '@app/store/workspaces/types';
import { SubmissionPath } from '@app/utils/conditional-logic';
import { OpenFormulierenExport, openFormulierenExportOf } from '@app/utils/open-formulieren-export';

export const WORKSPACES_REDUCER_PATH = 'workspacesApi';

export type ResponseExportStatus = 'queued' | 'running' | 'ready' | 'discarded' | 'expired' | 'erased' | 'failed' | 'cancelled' | 'streaming' | 'completed';

export interface ResponseExportDto {
    id: string;
    formId: string;
    kind: 'stream' | 'job';
    status: ResponseExportStatus;
    format: 'csv' | 'zip';
    createdAt?: string;
    rows?: number | null;
    fileName?: string | null;
    fileSize?: number | null;
    expiresAt?: string | null;
    downloadedAt?: string | null;
    downloadCount?: number;
    errorCode?: string | null;
    downloadUrl?: string;
    linkExpiresInSeconds?: number;
}

export interface StartResponseExportRequest {
    workspaceId: string;
    formId: string;
    /** column keys; none means every column */
    columns?: string[];
    /** the responses list's filters, by their names */
    submittedFrom?: string;
    submittedTo?: string;
    status?: string[];
    respondent?: 'anonymous' | 'known';
    formVersion?: number[];
    search?: string;
}

/** What starting an export answers: the file itself, or the job to follow. */
export type StartedResponseExport = { kind: 'file'; blob: Blob; mediaType: string } | { kind: 'job'; export: ResponseExportDto };

/** A refused export or download: the server's code and, for 429, when to try again. */
export interface ResponseExportRefusal {
    code?: string;
    message?: string;
    retryAfter?: number;
}

async function refusalOf(response: Response): Promise<ResponseExportRefusal> {
    const refusal = await response.json().catch(() => ({}));
    const wait = Number(response.headers.get('Retry-After'));
    return { ...(refusal && typeof refusal === 'object' ? refusal : {}), ...(Number.isFinite(wait) && wait > 0 ? { retryAfter: wait } : {}) };
}

/** Starting an export: the file (200), the job to follow (202), or the refusal's JSON. */
async function responseExportHandler(response: Response): Promise<any> {
    if (!response.ok) return refusalOf(response);
    if (response.status === 202) return { kind: 'job', export: await response.json() };
    return { kind: 'file', blob: await response.blob(), mediaType: response.headers.get('Content-Type') ?? '' };
}

/** Fetching a ready export: the file, or the refusal's JSON. */
async function responseExportFileHandler(response: Response): Promise<any> {
    return response.ok ? response.blob() : refusalOf(response);
}

const WORKSPACE_TAGS = 'WORKSPACE_TAG';
const SUBMISSION_TAG = 'SUBMISSION_TAG';

/**
 * One id as exactly one path segment: encoded (no "/", "?" or "#" gets
 * through), and never "." or "..", which a URL resolves as a step up the path.
 */
export function pathSegment(value: unknown): string {
    const text = encodeURIComponent(String(value ?? ''));
    return text === '.' || text === '..' ? text.replace(/\./g, '%252E') : text;
}

const WORKSPACE_UPDATE_TAG = 'WORKSPACE_UPDATE_TAG';
const GROUP_TAG = 'GROUP_TAG';
const RESPONDER_TAG = 'RESPONDER_TAG';
const FORM_TAG = 'FORM_TAG';

export interface InternalAnswersState {
    internalAnswers: Record<string, AnswerDto>;
    internalAnswersMeta: Record<string, InternalAnswerMeta>;
    internalAnswersVersion: number;
}

/** The workspace's AI consent (backend services/ai/consent.py). */
export interface WorkspaceAISettings {
    enabled: boolean;
    provider?: string | null;
    providerName?: string | null;
    enabledBy?: string | null;
    enabledAt?: string | null;
    defaultProvider: string;
    defaultProviderName: string;
    providers: Array<{ id: string; name: string; configured: boolean }>;
    canManage: boolean;
    learnPreferences: boolean;
}

export const WORKSPACE_PERMISSIONS_TAG = 'WORKSPACE_PERMISSIONS_TAG';

export const workspacesApi = createApi({
    reducerPath: WORKSPACES_REDUCER_PATH,
    tagTypes: [WORKSPACE_TAGS, WORKSPACE_UPDATE_TAG, SUBMISSION_TAG, GROUP_TAG, RESPONDER_TAG, FORM_TAG, 'AI_PROFILE_TAG', 'AI_MEMORY_TAG', 'API_KEYS_TAG', 'AI_SETTINGS_TAG', 'EMAIL_DOMAINS_TAG', 'SSO_TAG', 'SCIM_TAG', WORKSPACE_PERMISSIONS_TAG],
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    keepUnusedDataFor: 0,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        deleteResponse: builder.mutation<any, any>({
            query: (request) => ({
                // ids from a page's URL or a list: encoded, so one can never reach another path
                url: `/workspaces/${pathSegment(request.workspaceId)}/forms/${pathSegment(request.formId)}/response/${pathSegment(request.responseId)}`,
                method: 'DELETE'
            }),
            // The deletion-requests table (getWorkspaceAllSubmissions) and the
            // pending counter (getWorkspaceStats) only carry WORKSPACE_TAGS —
            // without it they kept showing the row as Pending after the delete.
            invalidatesTags: [SUBMISSION_TAG, WORKSPACE_TAGS]
        }),
        // Staff close a pending deletion request (privacy.manage): completed
        // deletes the copy stored here, declined keeps it with a fixed reason.
        closeDeletionRequest: builder.mutation<
            { formId: string; responseId: string; status: string; closedBy?: string | null; closedAt?: string | null; declineReason?: string | null },
            { workspaceId: string; formId: string; responseId: string; outcome: DeletionRequestOutcome; reason?: DeclineReason }
        >({
            query: ({ workspaceId, formId, responseId, outcome, reason }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/submissions/${encodeURIComponent(responseId)}/deletion-request/close`,
                method: 'POST',
                body: { outcome, ...(reason ? { reason } : {}) }
            }),
            // the lists and the pending counter (see deleteResponse)
            invalidatesTags: [SUBMISSION_TAG, WORKSPACE_TAGS]
        }),
        getWorkspaceNameSuggestions: builder.query<any, any>({
            query: (request) => ({
                url: `/workspaces/suggest-handle/${request.title}`,
                method: 'GET'
            })
        }),
        getWorkspaceNameAvailability: builder.query<any, any>({
            query: (request) => ({
                url: `/workspaces/check-handle-availability/${request.title}${request?.workspaceId ? `?workspace_id=${request?.workspaceId}` : ''}`,
                method: 'GET'
            })
        }),
        getWorkspaceByName: builder.query<WorkspaceDto, string>({
            query: (workspaceName) => ({
                url: '/workspaces',
                method: 'GET',
                params: { workspace_name: workspaceName }
            })
        }),
        verifyWorkspaceDomain: builder.query<any, string>({
            query: (workspaceId: string) => ({
                url: `/workspaces/${workspaceId}/verify-domain`,
                method: 'GET'
            })
        }),
        recheckWorkspaceDomain: builder.mutation<any, string>({
            query: (workspaceId: string) => ({
                url: `/workspaces/${workspaceId}/custom-domain/recheck`,
                method: 'POST'
            })
        }),
        getAllMineWorkspaces: builder.query<any, void>({
            query: () => ({
                url: '/workspaces/mine',
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        // the workspace selection screen: what the signed-in user may open
        // (the server's list; dropped with every other cache at sign-out)
        getWorkspaceSelection: builder.query<WorkspaceSelection, void>({
            query: () => ({
                url: '/workspaces/mine/selection',
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceForms: builder.query<Page<StandardFormDto>, any>({
            query: (body) => ({
                url: `/workspaces/${body.workspace_id}/forms${!!body.form_id ? `/${body.form_id}` : ''}`,
                method: 'GET',
                params: {
                    published: !!body.published,
                    pinned_only: body.pinned_only,
                    page: body.page,
                    size: body.size
                }
            }),
            providesTags: [WORKSPACE_TAGS, FORM_TAG]
        }),

        getWorkspaceForm: builder.query<StandardFormDto, IGetWorkspaceFormQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/forms/${query.custom_url}`,
                method: 'GET',
                params: {
                    published: !!query.published
                }
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceFormVersion: builder.query<StandardFormDto, { workspaceId: string; formId: string; version: number }>({
            query: ({ workspaceId, formId, version }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/versions/${version}`,
                method: 'GET'
            })
        }),
        getFormsSubmissions: builder.query<Page<StandardFormResponseDto>, IGetFormSubmissionsQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspaceId}/forms/${query.formId}/submissions`,
                params: {
                    request_for_deletion: query.requestedForDeletionOly,
                    page: query.page,
                    size: query.size,
                    dataOwnerIdentifier: query.dataOwnerIdentifier,
                    // keyset list: filters, sort and the cursor (undefined ones are not sent)
                    paging: query.paging,
                    sort_by: query.sort_by,
                    sort_order: query.sort_order,
                    submittedFrom: query.submittedFrom,
                    submittedTo: query.submittedTo,
                    status: query.status,
                    respondent: query.respondent,
                    formVersion: query.formVersion,
                    cursor: query.cursor
                },
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS, SUBMISSION_TAG]
        }),
        // The flow view's insights: each submission's path through the pages,
        // no answers (response.read). `savedAt` only keys the cache, so the
        // counts follow the rules as autosave stores them.
        getFormSubmissionPaths: builder.query<Array<SubmissionPath>, { workspaceId: string; formId: string; savedAt?: number }>({
            query: (query) => ({
                url: `/workspaces/${query.workspaceId}/forms/${query.formId}/submission-paths`,
                method: 'GET'
            })
        }),
        // The export of a form's responses (response.export, docs/response-export.md):
        // up to a few thousand responses come back as the file itself; more start a
        // background job and answer 202 with the export to follow. A refusal keeps
        // its JSON body (code, message) and, for 429, its Retry-After.
        startResponseExport: builder.mutation<StartedResponseExport, StartResponseExportRequest>({
            query: ({ workspaceId, formId, ...body }) => ({
                url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/exports`,
                method: 'POST',
                body,
                responseHandler: responseExportHandler
            })
        }),
        // The caller's own exports of the form that are running, ready or failed.
        getResponseExports: builder.query<ResponseExportDto[], { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/exports`, method: 'GET' })
        }),
        // One export; once its file is ready, a fresh signed link (valid five minutes).
        getResponseExport: builder.query<ResponseExportDto, { workspaceId: string; formId: string; exportId: string }>({
            query: ({ workspaceId, formId, exportId }) => ({ url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/exports/${pathSegment(exportId)}`, method: 'GET' })
        }),
        // Delete a ready file now (its requester only), so a new export can start before it expires.
        discardResponseExport: builder.mutation<null, { workspaceId: string; formId: string; exportId: string }>({
            query: ({ workspaceId, formId, exportId }) => ({ url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/exports/${pathSegment(exportId)}`, method: 'DELETE' })
        }),
        // The file of a ready export, through the link its status gave; it can be fetched again until it is deleted.
        downloadResponseExport: builder.mutation<Blob, { downloadUrl: string }>({
            query: ({ downloadUrl }) => ({ url: downloadUrl, method: 'GET', responseHandler: responseExportFileHandler })
        }),
        getWorkspaceSubmissions: builder.query<Page<StandardFormResponseDto>, IGetAllSubmissionsQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspaceId}/submissions`,
                params: {
                    request_for_deletion: query.requestedForDeletionOly,
                    page: query.page,
                    size: query.size
                },
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceAllSubmissions: builder.query<Page<StandardFormResponseDto>, IGetAllSubmissionsQuery>({
            query: (query: IGetAllSubmissionsQuery) => {
                return {
                    url: `/workspaces/${query.workspaceId}/all-submissions`,
                    params: {
                        data_subjects: query.data_subjects,
                        email: query.email,
                        request_for_deletion: query.requestedForDeletionOly,
                        dataOwnerIdentifier: query.dataOwnerIdentifier,
                        page: query.page || 1,
                        size: query.size || 50
                    },
                    method: 'GET'
                };
            },
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceResponders: builder.query<Page<WorkspaceResponderDto>, IGetAllSubmissionsQuery>({
            query: (query: IGetAllSubmissionsQuery) => {
                return {
                    url: `/workspaces/${query.workspaceId}/responders`,
                    params: {
                        email: query.email,
                        page: query.page || 1,
                        size: query.size || 50
                    },
                    method: 'GET'
                };
            },
            providesTags: [RESPONDER_TAG]
        }),
        getWorkspaceSubmission: builder.query<any, IGetWorkspaceSubmissionQuery>({
            query: (query) => ({
                // the response id comes from the page's URL: encoded, so it can never reach another path
                url: `/workspaces/${pathSegment(query.workspace_id)}/submissions/${pathSegment(query.submission_id)}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS, SUBMISSION_TAG]
        }),
        getWorkspaceSubmissionByUUID: builder.query<any, any>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/submissions/by-uuid/${query.submissionUUID}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS, SUBMISSION_TAG]
        }),
        // Staff fill in / clear a submission's internal ("office use") fields.
        // `answers` maps internal field id -> answer, or null to clear it.
        // `version` is the internalAnswersVersion the editor loaded; a stale one
        // gets a 409 whose body carries the current state (see internal-fields-panel).
        updateInternalAnswers: builder.mutation<InternalAnswersState, { workspaceId: string; formId: string; responseId: string; answers: Record<string, Record<string, any> | null>; version: number }>({
            query: ({ workspaceId, formId, responseId, answers, version }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/submissions/${responseId}/internal-answers`,
                method: 'PATCH',
                body: { answers, version }
            }),
            invalidatesTags: [SUBMISSION_TAG]
        }),
        // Workspace admins post an update (status and/or message) that the
        // submission's respondent sees. Returns the history, staff view.
        postRespondentFeedback: builder.mutation<StaffFeedback, { workspaceId: string; formId: string; responseId: string; status?: string | null; message?: string | null }>({
            query: ({ workspaceId, formId, responseId, status, message }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/submissions/${responseId}/feedback`,
                method: 'POST',
                body: { status: status || null, message: message || null }
            }),
            invalidatesTags: [SUBMISSION_TAG]
        }),
        getWorkspaceStats: builder.query<WorkspaceStatsDto, string>({
            query: (id) => ({
                url: `/workspaces/${id}/stats`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        requestWorkspaceSubmissionDeletion: builder.mutation<any, IGetWorkspaceSubmissionQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/submissions/${query.submission_id}`,
                method: 'DELETE',
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            }),
            invalidatesTags: [SUBMISSION_TAG, WORKSPACE_TAGS]
        }),
        requestWorkspaceSubmissionDeletionByUUID: builder.mutation<any, IGetWorkspaceSubmissionQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/submissions/by-uuid/${query.submission_id}`,
                method: 'DELETE',
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            }),
            invalidatesTags: [SUBMISSION_TAG, WORKSPACE_TAGS]
        }),
        searchWorkspaceForms: builder.query<Array<StandardFormDto>, ISearchWorkspaceFormsQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/forms/search`,
                method: 'POST',
                params: {
                    query: query.query,
                    published: !!query?.published
                }
            })
        }),
        patchFormSettings: builder.mutation<any, IPatchFormSettingsRequest>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/settings`,
                method: 'PATCH',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        duplicateForm: builder.mutation<any, { workspaceId: string; formId: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/duplicate`,
                method: 'POST',
                credentials: 'include'
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        // The form as an Open Formulieren import archive (OPEN_FORMULIEREN_EXPORT,
        // form.read): the zip, its file name and how many things the README lists.
        exportFormForOpenFormulieren: builder.mutation<OpenFormulierenExport, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({
                url: `/workspaces/${workspaceId}/forms/${formId}/open-formulieren-export`,
                method: 'GET',
                responseHandler: (response) => response.blob()
            }),
            transformResponse: (blob: Blob, meta) => openFormulierenExportOf(blob, meta?.response)
        }),
        deleteForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        createWorkspace: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces`,
                method: 'POST',
                body: request,
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            })
        }),
        patchExistingWorkspace: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}`,
                method: 'PATCH',
                body: request.body,
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        getAIProfile: builder.query<any, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/ai-profile`,
                method: 'GET'
            }),
            providesTags: ['AI_PROFILE_TAG']
        }),
        updateAIProfile: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/ai-profile`,
                method: 'PUT',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['AI_PROFILE_TAG']
        }),
        // The caller's effective permissions in a workspace (empty for a
        // non-member). Kept a while: many controls read it. The user id is
        // part of the cache key only, so one user never reads another's.
        getWorkspacePermissions: builder.query<{ permissions: Array<WorkspacePermission>; fieldRulesEnabled?: boolean; choiceLogicEnabled?: boolean; newQuestionTypesEnabled?: boolean; addressQuestionEnabled?: boolean; addressLookupEnabled?: boolean; signatureQuestionEnabled?: boolean; optionSourcesEnabled?: boolean; layoutContainersEnabled?: boolean; saveDraftsEnabled?: boolean; submissionsApiEnabled?: boolean }, { workspaceId: string; userId: string }>({
            query: ({ workspaceId }) => ({
                url: `/workspaces/${workspaceId}/permissions`,
                method: 'GET'
            }),
            keepUnusedDataFor: 300,
            providesTags: [WORKSPACE_PERMISSIONS_TAG]
        }),
        getAISettings: builder.query<WorkspaceAISettings, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/ai-settings`,
                method: 'GET'
            }),
            providesTags: ['AI_SETTINGS_TAG']
        }),
        updateAISettings: builder.mutation<WorkspaceAISettings, { workspace_id: string; body: { enabled: boolean; provider?: string } }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/ai-settings`,
                method: 'PUT',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['AI_SETTINGS_TAG']
        }),
        updateAIMemorySettings: builder.mutation<{ learnPreferences: boolean }, { workspace_id: string; body: { learnPreferences: boolean } }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/ai-memory/settings`,
                method: 'PUT',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['AI_SETTINGS_TAG']
        }),
        getAIMemory: builder.query<any, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/ai-memory`,
                method: 'GET'
            }),
            providesTags: ['AI_MEMORY_TAG']
        }),
        addAIMemoryEntry: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/ai-memory`,
                method: 'POST',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['AI_MEMORY_TAG']
        }),
        deleteAIMemoryEntry: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/ai-memory/${request.entry_id}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: ['AI_MEMORY_TAG']
        }),
        getAPIKeys: builder.query<any, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/api-keys`,
                method: 'GET'
            }),
            providesTags: ['API_KEYS_TAG']
        }),
        createAPIKey: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/api-keys`,
                method: 'POST',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['API_KEYS_TAG']
        }),
        revokeAPIKey: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/api-keys/${request.key_id}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            // the SSO page lists the keys that predate the requirement
            invalidatesTags: ['API_KEYS_TAG', 'SSO_TAG']
        }),
        // Verified email domains (docs/verified-domains.md); owner/admins only.
        getEmailDomains: builder.query<Array<WorkspaceDomainDto>, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/domains`,
                method: 'GET'
            }),
            providesTags: ['EMAIL_DOMAINS_TAG']
        }),
        claimEmailDomain: builder.mutation<WorkspaceDomainDto, { workspace_id: string; domain: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/domains`,
                method: 'POST',
                body: { domain: request.domain },
                credentials: 'include'
            }),
            invalidatesTags: ['EMAIL_DOMAINS_TAG']
        }),
        verifyEmailDomain: builder.mutation<WorkspaceDomainDto, { workspace_id: string; domain_id: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/domains/${request.domain_id}/verify`,
                method: 'POST',
                credentials: 'include'
            }),
            invalidatesTags: ['EMAIL_DOMAINS_TAG']
        }),
        deleteEmailDomain: builder.mutation<void, { workspace_id: string; domain_id: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/domains/${request.domain_id}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: ['EMAIL_DOMAINS_TAG']
        }),
        // SCIM directory sync (docs/sso.md); viewing needs security.manage,
        // every change is owner only.
        getWorkspaceScim: builder.query<ScimOverviewDto, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/scim`,
                method: 'GET',
                credentials: 'include'
            }),
            providesTags: ['SCIM_TAG']
        }),
        createScimDirectory: builder.mutation<ScimCredentialsDto, { workspace_id: string; body: CreateScimDirectoryRequest }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/scim/directory`,
                method: 'POST',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['SCIM_TAG']
        }),
        rotateScimToken: builder.mutation<ScimCredentialsDto, { workspace_id: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/scim/directory/rotate`,
                method: 'POST',
                credentials: 'include'
            }),
            invalidatesTags: ['SCIM_TAG']
        }),
        deleteScimDirectory: builder.mutation<{ reEnabled: number; leftDisabled: number }, { workspace_id: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/scim/directory`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: ['SCIM_TAG']
        }),
        setScimGroupRole: builder.mutation<ScimGroupDto, { workspace_id: string; group_id: string; role: string | null }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/scim/groups/${request.group_id}`,
                method: 'PUT',
                body: { role: request.role },
                credentials: 'include'
            }),
            invalidatesTags: ['SCIM_TAG']
        }),
        resyncScimDirectory: builder.mutation<ScimResyncDto, { workspace_id: string; force?: boolean }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/scim/resync`,
                method: 'POST',
                body: { force: !!request.force },
                credentials: 'include'
            }),
            invalidatesTags: ['SCIM_TAG']
        }),
        cleanupScimDirectory: builder.mutation<ScimDirectoryDto, { workspace_id: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/scim/directory/cleanup`,
                method: 'POST',
                credentials: 'include'
            }),
            invalidatesTags: ['SCIM_TAG']
        }),
        // Single sign-on (docs/sso.md); owner/admins only (security.manage).
        getWorkspaceSso: builder.query<SsoOverviewDto, string>({
            query: (workspaceId) => ({
                url: `/workspaces/${workspaceId}/sso`,
                method: 'GET'
            }),
            providesTags: ['SSO_TAG']
        }),
        // A page of the owner break-glass log (older than the cursor); owners and admins.
        getSsoAuditPage: builder.query<SsoAuditPageDto, { workspace_id: string; cursor: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/sso/audit`,
                params: { cursor: request.cursor },
                credentials: 'include'
            })
        }),
        createSsoConnection: builder.mutation<SsoConnectionDto, { workspace_id: string; body: CreateSsoConnectionRequest }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/sso/connections`,
                method: 'POST',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['SSO_TAG']
        }),
        setSsoConnectionEnabled: builder.mutation<SsoConnectionDto, { workspace_id: string; connection_id: string; enabled: boolean }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/sso/connections/${request.connection_id}/${request.enabled ? 'enable' : 'disable'}`,
                method: 'POST',
                credentials: 'include'
            }),
            invalidatesTags: ['SSO_TAG']
        }),
        deleteSsoConnection: builder.mutation<void, { workspace_id: string; connection_id: string }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/sso/connections/${request.connection_id}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: ['SSO_TAG']
        }),
        updateSsoSettings: builder.mutation<SsoSettingsDto, { workspace_id: string; body: UpdateSsoSettingsRequest }>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/sso/settings`,
                method: 'PUT',
                body: request.body,
                credentials: 'include'
            }),
            invalidatesTags: ['SSO_TAG', 'SCIM_TAG']
        }),
        patchWorkspaceThemes: builder.mutation<any, any>({
            // Replaces the workspace's saved custom form themes (full-list PATCH).
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/theme-presets`,
                method: 'PATCH',
                body: request.body,
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        deleteWorkspaceDomain: builder.mutation<any, any>({
            query: (workspace_id) => ({
                url: `/workspaces/${workspace_id}/custom-domain`,
                method: 'DELETE'
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        createRespondersGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `${request.workspace_id}/responder-groups`,
                method: 'POST',
                params: {
                    name: request.groupInfo.name,
                    description: request.groupInfo.description,
                    regex: request.groupInfo.regex,
                    form_id: request.groupInfo.formId
                },
                body: request.groupInfo.emails
            }),
            invalidatesTags: [GROUP_TAG]
        }),
        getRespondersGroup: builder.query<any, any>({
            query: (query) => ({
                url: `${query.workspaceId}/responder-groups/${query.groupId}`,
                method: 'GET'
            }),
            providesTags: [GROUP_TAG, RESPONDER_TAG, FORM_TAG]
        }),
        getAllRespondersGroup: builder.query<Array<ResponderGroupDto>, string>({
            query: (workspace_id) => ({
                url: `${workspace_id}/responder-groups`,
                method: 'GET'
            }),
            providesTags: [GROUP_TAG, RESPONDER_TAG, FORM_TAG]
        }),
        deleteResponderGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `${request.workspaceId}/responder-groups/${request.groupId}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: [GROUP_TAG]
        }),
        AddResponderOnGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `${request.workspaceId}/responder-groups/${request.groupId}/emails`,
                method: 'PATCH',
                body: request.emails
            }),
            invalidatesTags: [RESPONDER_TAG]
        }),
        deleteResponderFromGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `${request.workspaceId}/responder-groups/${request.groupId}/emails`,
                method: 'DELETE',
                body: request.emails
            }),
            invalidatesTags: [RESPONDER_TAG]
        }),
        addFormOnGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `workspaces/${request.workspaceId}/forms/${request.formId}/groups/add`,
                method: 'PATCH',
                body: {
                    group_ids: request.groups
                }
            }),
            invalidatesTags: [FORM_TAG, GROUP_TAG]
        }),
        deleteGroupForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `workspaces/${request.workspaceId}/forms/${request.formId}/groups`,
                params: {
                    group_id: request.groupId
                },
                method: 'DELETE'
            }),
            invalidatesTags: [FORM_TAG, GROUP_TAG, RESPONDER_TAG]
        }),
        updateResponderGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `${request.workspaceId}/responder-groups/${request.groupId}`,
                params: {
                    name: request.groupInfo.name,
                    description: request.groupInfo.description,
                    regex: request.groupInfo.regex
                },
                body: request.groupInfo.emails,
                method: 'PATCH'
            }),
            invalidatesTags: [GROUP_TAG]
        })
    })
});

export const {
    useDeleteWorkspaceDomainMutation,
    useGetWorkspaceByNameQuery,
    useGetWorkspaceFormsQuery,
    useGetWorkspaceFormQuery,
    useGetWorkspaceStatsQuery,
    useGetWorkspaceSubmissionsQuery,
    useGetWorkspaceAllSubmissionsQuery,
    useGetWorkspaceRespondersQuery,
    useGetWorkspaceSubmissionQuery,
    useLazyGetWorkspaceSubmissionQuery,
    useLazyGetWorkspaceFormVersionQuery,
    useLazyGetWorkspaceNameSuggestionsQuery,
    useLazyGetWorkspaceNameAvailabilityQuery,
    useLazySearchWorkspaceFormsQuery,
    useGetFormsSubmissionsQuery,
    useDeleteResponseMutation,
    useCloseDeletionRequestMutation,
    usePatchFormSettingsMutation,
    useDeleteFormMutation,
    useCreateWorkspaceMutation,
    usePatchExistingWorkspaceMutation,
    usePatchWorkspaceThemesMutation,
    useGetAIProfileQuery,
    useUpdateAIProfileMutation,
    useGetAISettingsQuery,
    useGetWorkspacePermissionsQuery,
    useUpdateAISettingsMutation,
    useUpdateAIMemorySettingsMutation,
    useGetAIMemoryQuery,
    useAddAIMemoryEntryMutation,
    useDeleteAIMemoryEntryMutation,
    useGetAPIKeysQuery,
    useCreateAPIKeyMutation,
    useRevokeAPIKeyMutation,
    useGetEmailDomainsQuery,
    useGetWorkspaceSsoQuery,
    useLazyGetSsoAuditPageQuery,
    useCreateSsoConnectionMutation,
    useSetSsoConnectionEnabledMutation,
    useDeleteSsoConnectionMutation,
    useUpdateSsoSettingsMutation,
    useGetWorkspaceScimQuery,
    useCreateScimDirectoryMutation,
    useRotateScimTokenMutation,
    useDeleteScimDirectoryMutation,
    useSetScimGroupRoleMutation,
    useResyncScimDirectoryMutation,
    useCleanupScimDirectoryMutation,
    useClaimEmailDomainMutation,
    useVerifyEmailDomainMutation,
    useDeleteEmailDomainMutation,
    useDuplicateFormMutation,
    useExportFormForOpenFormulierenMutation,
    useGetAllMineWorkspacesQuery,
    useGetWorkspaceSelectionQuery,
    useRequestWorkspaceSubmissionDeletionMutation,
    useCreateRespondersGroupMutation,
    useGetRespondersGroupQuery,
    useGetAllRespondersGroupQuery,
    useDeleteResponderGroupMutation,
    useAddResponderOnGroupMutation,
    useAddFormOnGroupMutation,
    useDeleteResponderFromGroupMutation,
    useDeleteGroupFormMutation,
    useUpdateResponderGroupMutation,
    useGetWorkspaceSubmissionByUUIDQuery,
    useLazyGetWorkspaceSubmissionByUUIDQuery,
    useRequestWorkspaceSubmissionDeletionByUUIDMutation,
    useGetFormSubmissionPathsQuery,
    useStartResponseExportMutation,
    useGetResponseExportsQuery,
    useGetResponseExportQuery,
    useDownloadResponseExportMutation,
    useDiscardResponseExportMutation,
    useVerifyWorkspaceDomainQuery,
    useRecheckWorkspaceDomainMutation,
    useUpdateInternalAnswersMutation,
    usePostRespondentFeedbackMutation
} = workspacesApi;
