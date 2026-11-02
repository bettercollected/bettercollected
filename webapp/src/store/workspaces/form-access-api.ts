import { pathSegment, workspacesApi } from '@app/store/workspaces/api';

// Form-level access (backend controllers/form_access_router.py): who on the team may open one form, the teams
// that grants can name, and a member's own view of what they hold. Every route but the read of a form's access
// answers 422 `form_access_off` while the server's FORM_ACCESS_ENABLED is off; the webapp asks for none of them
// then (`useWorkspacePermissions().formAccessEnabled`). The server decides every rule; nothing here is trusted.

export type GrantRole = 'EDITOR' | 'REVIEWER' | 'VIEWER';
export type GrantSubjectType = 'user' | 'group';
export type FormAccessMode = 'workspace' | 'restricted';

export interface FormGrantDto {
    id: string;
    subjectType: GrantSubjectType;
    subjectId: string;
    role: GrantRole;
    export: boolean;
    /** A team's name, or a person's when the member directory knows it. */
    name?: string | null;
    /** The person's membership is deactivated: the grant does nothing until they are active again. */
    disabled?: boolean;
    createdBy?: string | null;
    createdAt?: string | null;
    /** The display name of whoever gave the grant; none when they are no longer a member or the directory could not name them. */
    grantedBy?: string | null;
    /** A team grant only: how many people the team has now. Absent for a person (and from a server that does not send it). */
    memberCount?: number | null;
    /** Only in a member's own access view: the form the grant is on. `formTitle` is null for a form the reader may not open. */
    formId?: string | null;
    formTitle?: string | null;
}

export interface FormAccessDto {
    enabled: boolean;
    /** The stored choice; none while never chosen (a Private form then counts as restricted). */
    accessMode?: FormAccessMode | null;
    restricted?: boolean;
    myPermissions?: string[];
    source?: string | null;
    /** The caller may change the mode and the circle. */
    canManage?: boolean;
    /** Only for whoever may share the form. */
    grants?: FormGrantDto[] | null;
}

export interface TeamDto {
    id: string;
    name: string;
    description?: string | null;
    source?: string;
    memberCount: number;
    createdAt?: string | null;
}

export interface TeamMemberDto {
    userId: string;
    name?: string | null;
    role?: string | null;
}

export interface TeamDetailDto extends TeamDto {
    members: TeamMemberDto[];
    formCount: number;
}

export interface MemberAccessDto {
    teams: TeamDto[];
    grants: FormGrantDto[];
}

/** The picker for whoever may share a form but not list the workspace's members (`GET .../forms/{id}/access/candidates`). Names and ids only. */
export interface FormAccessCandidatesDto {
    members: Array<{ id: string; name: string }>;
    teams: Array<{ id: string; name: string; memberCount: number }>;
}

/** The dry run of a mode change (`GET .../forms/{id}/access/impact?mode=`): a count, never names. */
export interface FormAccessImpactDto {
    mode: FormAccessMode;
    membersLosingAccess: number;
}

export interface GrantRequest {
    subjectType: GrantSubjectType;
    subjectId: string;
    role: GrantRole;
    export: boolean;
}

/** The server's own limits (backend services/form_access/admin.py), shown in the Teams tab. */
export const MAX_TEAMS = 20;
export const MAX_TEAM_MEMBERS = 500;

const FORM_ACCESS_TAG = 'FORM_ACCESS_TAG';
const TEAMS_TAG = 'TEAMS_TAG';
const MEMBER_ACCESS_TAG = 'MEMBER_ACCESS_TAG';

export const formAccessApi = workspacesApi.enhanceEndpoints({ addTagTypes: [FORM_ACCESS_TAG, TEAMS_TAG, MEMBER_ACCESS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        getFormAccess: builder.query<FormAccessDto, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/access`, method: 'GET' }),
            providesTags: (_result, _error, { formId }) => [{ type: FORM_ACCESS_TAG, id: formId }]
        }),
        getFormAccessCandidates: builder.query<FormAccessCandidatesDto, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/access/candidates`, method: 'GET' }),
            providesTags: (_result, _error, { formId }) => [{ type: FORM_ACCESS_TAG, id: formId }, TEAMS_TAG]
        }),
        getFormAccessImpact: builder.query<FormAccessImpactDto, { workspaceId: string; formId: string; mode: FormAccessMode }>({
            query: ({ workspaceId, formId, mode }) => ({ url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/access/impact`, method: 'GET', params: { mode } }),
            providesTags: (_result, _error, { formId }) => [{ type: FORM_ACCESS_TAG, id: formId }, TEAMS_TAG]
        }),
        setFormAccessMode: builder.mutation<FormAccessDto, { workspaceId: string; formId: string; mode: FormAccessMode }>({
            query: ({ workspaceId, formId, mode }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/access/mode`, method: 'PUT', body: { mode } }),
            invalidatesTags: (_result, _error, { formId }) => [{ type: FORM_ACCESS_TAG, id: formId }, MEMBER_ACCESS_TAG]
        }),
        putFormGrant: builder.mutation<FormGrantDto, { workspaceId: string; formId: string; grant: GrantRequest }>({
            query: ({ workspaceId, formId, grant }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/grants`, method: 'PUT', body: grant }),
            invalidatesTags: (_result, _error, { formId }) => [{ type: FORM_ACCESS_TAG, id: formId }, TEAMS_TAG, MEMBER_ACCESS_TAG]
        }),
        deleteFormGrant: builder.mutation<void, { workspaceId: string; formId: string; grantId: string }>({
            query: ({ workspaceId, formId, grantId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/grants/${grantId}`, method: 'DELETE' }),
            invalidatesTags: (_result, _error, { formId }) => [{ type: FORM_ACCESS_TAG, id: formId }, TEAMS_TAG, MEMBER_ACCESS_TAG]
        }),

        getTeams: builder.query<TeamDto[], string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/member-groups`, method: 'GET' }),
            providesTags: [TEAMS_TAG]
        }),
        getTeam: builder.query<TeamDetailDto, { workspaceId: string; teamId: string }>({
            query: ({ workspaceId, teamId }) => ({ url: `/workspaces/${workspaceId}/member-groups/${teamId}`, method: 'GET' }),
            providesTags: [TEAMS_TAG]
        }),
        createTeam: builder.mutation<TeamDto, { workspaceId: string; name: string; description?: string }>({
            query: ({ workspaceId, name, description }) => ({ url: `/workspaces/${workspaceId}/member-groups`, method: 'POST', body: { name, ...(description ? { description } : {}) } }),
            invalidatesTags: [TEAMS_TAG]
        }),
        renameTeam: builder.mutation<TeamDto, { workspaceId: string; teamId: string; name: string }>({
            query: ({ workspaceId, teamId, name }) => ({ url: `/workspaces/${workspaceId}/member-groups/${teamId}`, method: 'PATCH', body: { name } }),
            invalidatesTags: [TEAMS_TAG, MEMBER_ACCESS_TAG]
        }),
        deleteTeam: builder.mutation<void, { workspaceId: string; teamId: string }>({
            query: ({ workspaceId, teamId }) => ({ url: `/workspaces/${workspaceId}/member-groups/${teamId}`, method: 'DELETE' }),
            invalidatesTags: [TEAMS_TAG, MEMBER_ACCESS_TAG]
        }),
        addTeamMember: builder.mutation<void, { workspaceId: string; teamId: string; memberId: string }>({
            query: ({ workspaceId, teamId, memberId }) => ({ url: `/workspaces/${workspaceId}/member-groups/${teamId}/members/${memberId}`, method: 'PUT' }),
            invalidatesTags: [TEAMS_TAG, MEMBER_ACCESS_TAG]
        }),
        removeTeamMember: builder.mutation<void, { workspaceId: string; teamId: string; memberId: string }>({
            query: ({ workspaceId, teamId, memberId }) => ({ url: `/workspaces/${workspaceId}/member-groups/${teamId}/members/${memberId}`, method: 'DELETE' }),
            invalidatesTags: [TEAMS_TAG, MEMBER_ACCESS_TAG]
        }),
        getMemberAccess: builder.query<MemberAccessDto, { workspaceId: string; memberId: string }>({
            query: ({ workspaceId, memberId }) => ({ url: `/workspaces/${workspaceId}/members/${memberId}/access`, method: 'GET' }),
            providesTags: [MEMBER_ACCESS_TAG]
        })
    })
});

export const {
    useGetFormAccessQuery,
    useGetFormAccessCandidatesQuery,
    useGetFormAccessImpactQuery,
    useSetFormAccessModeMutation,
    usePutFormGrantMutation,
    useDeleteFormGrantMutation,
    useGetTeamsQuery,
    useGetTeamQuery,
    useCreateTeamMutation,
    useRenameTeamMutation,
    useDeleteTeamMutation,
    useAddTeamMemberMutation,
    useRemoveTeamMemberMutation,
    useGetMemberAccessQuery
} = formAccessApi;
