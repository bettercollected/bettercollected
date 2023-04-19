import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const WORKSPACE_INVITATIONS_PATH = 'membersNInvitationsApi';
export const membersNInvitationsApi = createApi({
    reducerPath: WORKSPACE_INVITATIONS_PATH,
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
        })
    })
});

export const { useRespondToWorkspaceInvitationMutation } = membersNInvitationsApi;
