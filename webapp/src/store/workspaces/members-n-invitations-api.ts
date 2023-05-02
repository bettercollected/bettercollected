import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const WORKSPACE_INVITATIONS_PATH = 'membersNInvitationsApi';

const WORKSPACE_INVITATIONS_TAG = 'WORKSPACE_INVITATIONS_TAG';
const WORKSPACE_MEMBERS_TAG = 'WORKSPACE_MEMBERS_TAG';
export const membersNInvitationsApi = createApi({
    reducerPath: WORKSPACE_INVITATIONS_PATH,
    tagTypes: [WORKSPACE_INVITATIONS_TAG, WORKSPACE_MEMBERS_TAG],
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    keepUnusedDataFor: 0,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST + '/workspaces',
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        respondToWorkspaceInvitation: builder.mutation<any, any>({
            query: (request) => ({
                url: `/${request.workspaceId}/members/invitations/${request.invitationToken}`,
                method: 'POST',
                params: {
                    response_status: request.responseStatus
                }
            })
        }),
        getWorkspaceMembers: builder.query<Array<any>, any>({
            query: (request) => ({
                url: `/${request.workspaceId}/members`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_MEMBERS_TAG]
        }),
        deleteWorkspaceMember: builder.mutation<any, any>({
            query: (request) => ({
                url: `/${request.workspaceId}/members/${request.userId}`,
                method: 'DELETE'
            }),
            invalidatesTags: [WORKSPACE_MEMBERS_TAG, WORKSPACE_INVITATIONS_TAG]
        }),
        deleteWorkspaceInvitation: builder.mutation<any, any>({
            query: (request) => ({
                url: `/${request.workspaceId}/members/invitations/${request.invitationToken}`,
                method: 'DELETE'
            }),
            invalidatesTags: [WORKSPACE_INVITATIONS_TAG]
        }),
        getWorkspaceMembersInvitations: builder.query<any, any>({
            query: (request) => ({
                url: `/${request.workspaceId}/members/invitations`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_INVITATIONS_TAG]
        }),
        inviteToWorkspace: builder.mutation<any, any>({
            query: (request) => ({
                url: `/${request.workspaceId}/members/invitations`,
                method: 'POST',
                body: request.body
            }),
            invalidatesTags: [WORKSPACE_INVITATIONS_TAG]
        })
    })
});

export const { useRespondToWorkspaceInvitationMutation, useGetWorkspaceMembersQuery, useGetWorkspaceMembersInvitationsQuery, useInviteToWorkspaceMutation, useDeleteWorkspaceMemberMutation, useDeleteWorkspaceInvitationMutation } = membersNInvitationsApi;
