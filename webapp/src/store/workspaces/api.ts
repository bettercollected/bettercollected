import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { StandardFormDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { IGenericAPIResponse } from '@app/models/dtos/genericResponse';
import { GoogleFormDto, GoogleMinifiedFormDto } from '@app/models/dtos/googleForm';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { IGetWorkspaceFormQuery, IGetWorkspaceSubmissionQuery, IPatchFormSettingsRequest, ISearchWorkspaceFormsQuery } from '@app/store/workspaces/types';

export const WORKSPACES_REDUCER_PATH = 'workspacesApi';

const WORKSPACE_TAGS = 'WORKSPACE_TAG';
const WORKSPACE_UPDATE_TAG = 'WORKSPACE_UPDATE_TAG';

interface ImportFormQueryInterface {
    workspaceId: string;

    body: {
        form: GoogleFormDto;
        response_data_owner: string;
    };
}

export const workspacesApi = createApi({
    reducerPath: WORKSPACES_REDUCER_PATH,
    tagTypes: [WORKSPACE_TAGS, WORKSPACE_UPDATE_TAG],
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
        getMinifiedForms: builder.query<IGenericAPIResponse<Array<GoogleMinifiedFormDto>>, void>({
            query: () => ({
                url: '/forms/import',
                method: 'GET'
            })
        }),
        getGoogleForm: builder.query<IGenericAPIResponse<GoogleFormDto>, string>({
            query: (id) => ({
                url: `/forms/import/${id}`,
                method: 'GET'
            })
        }),
        importForm: builder.mutation<any, ImportFormQueryInterface>({
            query: (request) => ({
                url: `workspaces/${request.workspaceId}/forms/import`,
                method: 'POST',
                body: request.body
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        getWorkspace: builder.query<WorkspaceDto, { workspace_id: string }>({
            query: (body) => ({
                url: `/workspaces`,
                method: 'GET',
                params: { workspace_id: body.workspace_id }
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceForms: builder.query<IGenericAPIResponse<Array<StandardFormDto>>, any>({
            query: (body) => ({
                url: `/workspaces/${body.workspace_id}/forms`,
                method: 'GET',
                params: !!body.form_id ? { form_id: body.form_id } : {}
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
        getWorkspaceAllSubmissions: builder.query<IGenericAPIResponse<Array<StandardFormResponseDto>>, string>({
            query: (id) => ({
                url: `/workspaces/${id}/allSubmissions`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceSubmission: builder.query<IGenericAPIResponse<any>, IGetWorkspaceSubmissionQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/submissions/${query.submission_id}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        searchWorkspaceForms: builder.mutation<IGenericAPIResponse<Array<StandardFormDto>>, ISearchWorkspaceFormsQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/forms/search?query=${query.query}`,
                method: 'POST'
            })
        }),
        patchFormSettings: builder.mutation<any, IPatchFormSettingsRequest>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/settings`,
                method: 'PATCH',
                body: request.body,
                credentials: 'include'
            })
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
            })
            // providesTags: [WORKSPACE_UPDATE_TAG]
        })
    })
});

export const {
    useGetMinifiedFormsQuery,
    useLazyGetGoogleFormQuery,
    useImportFormMutation,
    useGetWorkspaceQuery,
    useGetWorkspaceFormsQuery,
    useGetWorkspaceFormQuery,
    useLazyGetWorkspaceFormsQuery,
    useGetWorkspaceSubmissionsQuery,
    useGetWorkspaceAllSubmissionsQuery,
    useGetWorkspaceSubmissionQuery,
    useLazyGetWorkspaceSubmissionQuery,
    useSearchWorkspaceFormsMutation,
    usePatchFormSettingsMutation,
    useCreateWorkspaceMutation,
    usePatchExistingWorkspaceMutation
} = workspacesApi;
