import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { StandardFormDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { IGenericAPIResponse } from '@app/models/dtos/genericResponse';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { IGetWorkspaceFormQuery, IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';

export const WORKSPACES_REDUCER_PATH = 'workspacesApi';

const WORKSPACE_TAGS = 'WORKSPACE_TAG';
export const workspacesApi = createApi({
    reducerPath: WORKSPACES_REDUCER_PATH,
    tagTypes: [WORKSPACE_TAGS],
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    keepUnusedDataFor: 0,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getWorkspace: builder.query<WorkspaceDto, { workspace_id: string }>({
            query: (body) => ({
                url: `/workspaces`,
                method: 'GET',
                params: { workspace_id: body.workspace_id }
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceForms: builder.query<IGenericAPIResponse<Array<StandardFormDto>>, string>({
            query: (id) => ({
                url: `/workspaces/${id}/forms`,
                method: 'GET',
                params: {}
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceForm: builder.query<IGenericAPIResponse<StandardFormDto>, IGetWorkspaceFormQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/forms/${query.custom_url}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceSubmissions: builder.query<IGenericAPIResponse<Array<StandardFormResponseDto>>, string>({
            query: (id) => ({
                url: `/workspaces/${id}/submissions`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceSubmission: builder.query<IGenericAPIResponse<Array<StandardFormResponseDto>>, IGetWorkspaceSubmissionQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/submissions/${query.submission_id}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        })
    })
});

export const { useGetWorkspaceQuery, useGetWorkspaceFormsQuery, useGetWorkspaceFormQuery, useGetWorkspaceSubmissionsQuery, useGetWorkspaceSubmissionQuery } = workspacesApi;
