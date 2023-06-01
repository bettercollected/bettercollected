import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { StandardFormDto, StandardFormResponseDto, WorkspaceResponderDto } from '@app/models/dtos/form';
import { Page } from '@app/models/dtos/page';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { IGetAllSubmissionsQuery, IGetFormSubmissionsQuery, IGetWorkspaceFormQuery, IGetWorkspaceSubmissionQuery, IPatchFormSettingsRequest, ISearchWorkspaceFormsQuery } from '@app/store/workspaces/types';

export const WORKSPACES_REDUCER_PATH = 'workspacesApi';

const WORKSPACE_TAGS = 'WORKSPACE_TAG';
const SUBMISSION_TAG = 'SUBMISSION_TAG';
const WORKSPACE_UPDATE_TAG = 'WORKSPACE_UPDATE_TAG';
const GROUP_TAGS = 'GROUP_TAG';
interface ImportFormQueryInterface {
    workspaceId: string;
    provider: string;

    body: {
        form: any;
        response_data_owner: string;
    };
}

export const workspacesApi = createApi({
    reducerPath: WORKSPACES_REDUCER_PATH,
    tagTypes: [WORKSPACE_TAGS, WORKSPACE_UPDATE_TAG, SUBMISSION_TAG, GROUP_TAGS],
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
        getMinifiedForms: builder.query<Array<any>, { provider: string }>({
            query: (request) => ({
                url: `/${request.provider}/import`,
                method: 'GET',
                refetchOnMountOrArgChange: true,
                refetchOnReconnect: true,
                refetchOnFocus: true
            }),
            transformResponse(baseQueryReturnValue: Array<any>, meta, arg) {
                const provider = arg?.provider;
                const returnValue: Array<{ label: string; formId: string }> = [];
                baseQueryReturnValue.forEach((data) => {
                    if (provider === 'google') {
                        const parsedForm = { label: data?.name, formId: data?.id };
                        returnValue.push(parsedForm);
                    }
                    if (provider === 'typeform') {
                        const parsedForm = { label: data?.title, formId: data?.id };
                        returnValue.push(parsedForm);
                    }
                });

                return returnValue;
            }
        }),
        getSingleFormFromProvider: builder.query<any, { provider: string; formId: string }>({
            query: ({ provider, formId }) => ({
                url: `/${provider}/import/${formId}`,
                method: 'GET',
                refetchOnMountOrArgChange: true,
                refetchOnReconnect: true,
                refetchOnFocus: true
            }),
            transformResponse(baseQueryReturnValue: any, meta, arg) {
                const provider = arg?.provider;
                const fieldItems: Array<{ label: string; questionId: string }> = [];
                const returnValue = baseQueryReturnValue;
                if (provider === 'google') {
                    const formItems = baseQueryReturnValue?.items ?? [];
                    if (formItems && Array.isArray(formItems)) {
                        formItems.forEach((item) => {
                            if (!item?.questionItem?.question?.questionId) return;
                            const field = {
                                label: item.title,
                                questionId: item?.questionItem?.question?.questionId
                            };
                            fieldItems.push(field);
                        });

                        // We're appending clientFormItems in the API response to set parsed field items
                        // We need to remove this before making POST request when importing the form
                        returnValue['clientFormItems'] = fieldItems;
                    }
                }
                if (provider === 'typeform') {
                    const formItems = baseQueryReturnValue?.fields ?? [];
                    if (formItems && Array.isArray(formItems)) {
                        const emailFieldsArray = ['short_text', 'long_text', 'phone_number', 'email'];
                        formItems
                            .filter((field: any) => emailFieldsArray.includes(field.type))
                            .forEach((item: any) => {
                                if (!item?.id) return;
                                const field = {
                                    label: item.title,
                                    questionId: item?.id
                                };
                                fieldItems.push(field);
                            });

                        // We're appending clientFormItems in the API response to set parsed field items
                        // We need to remove this before making POST request when importing the form
                        returnValue['clientFormItems'] = fieldItems;
                    }
                }

                return returnValue;
            }
        }),
        importForm: builder.mutation<any, ImportFormQueryInterface>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/import/${request.provider}`,
                method: 'POST',
                body: request.body
            }),
            invalidatesTags: [WORKSPACE_TAGS]
        }),
        getWorkspace: builder.query<WorkspaceDto, string>({
            query: (body) => ({
                url: `/workspaces/${body}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getAllMineWorkspaces: builder.query<any, void>({
            query: () => ({
                url: '/workspaces/mine',
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceForms: builder.query<Page<StandardFormDto>, any>({
            query: (body) => ({
                url: `/workspaces/${body.workspace_id}/forms${!!body.form_id ? `/${body.form_id}` : ''}`,
                method: 'GET',
                params: {
                    page: body.page,
                    size: body.size
                }
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getWorkspaceForm: builder.query<StandardFormDto, IGetWorkspaceFormQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/forms/${query.custom_url}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
        }),
        getFormsSubmissions: builder.query<Page<StandardFormResponseDto>, IGetFormSubmissionsQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspaceId}/forms/${query.formId}/submissions`,
                params: {
                    request_for_deletion: query.requestedForDeletionOly,
                    page: query.page,
                    size: query.size
                },
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS]
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
        getWorkspaceAllSubmissions: builder.query<Page<StandardFormResponseDto | WorkspaceResponderDto>, IGetAllSubmissionsQuery>({
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
        getWorkspaceResponders: builder.query<Page<StandardFormResponseDto | WorkspaceResponderDto>, IGetAllSubmissionsQuery>({
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
            }
        }),
        getWorkspaceSubmission: builder.query<any, IGetWorkspaceSubmissionQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspace_id}/submissions/${query.submission_id}`,
                method: 'GET'
            }),
            providesTags: [WORKSPACE_TAGS, SUBMISSION_TAG]
        }),
        getWorkspaceStats: builder.query<any, string>({
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
        searchWorkspaceForms: builder.mutation<Array<StandardFormDto>, ISearchWorkspaceFormsQuery>({
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
            }),
            invalidatesTags: [WORKSPACE_TAGS]
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
        patchTheme: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}/theme`,
                method: 'PATCH',
                body: request.body,
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            })
        }),
        patchWorkspacePolicies: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspace_id}`,
                method: 'PATCH',
                body: request.body,
                credentials: 'include',
                headers: {
                    'Access-control-allow-origin': environments.API_ENDPOINT_HOST
                }
            })
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
                    description: request.groupInfo.description
                },
                body: request.groupInfo.emails
            }),
            invalidatesTags: [GROUP_TAGS]
        }),
        getRespondersGroup: builder.query<any, any>({
            query: (query) => ({
                url: `${query.workspace_id}/responder-groups/${query.group_id}`,
                method: 'GET'
            }),
            providesTags: [GROUP_TAGS]
        }),
        getAllRespondersGroup: builder.query<any, any>({
            query: (workspace_id) => ({
                url: `${workspace_id}/responder-groups`,
                method: 'GET'
            }),
            providesTags: [GROUP_TAGS]
        }),
        deleteResponderGroup: builder.mutation<any, any>({
            query: (request) => ({
                url: `${request.workspaceId}/responder-groups/${request.groupId}`,
                method: 'DELETE',
                credentials: 'include'
            }),
            invalidatesTags: [GROUP_TAGS]
        }),
        updateResponderGroupEmails: builder.query<any, any>({
            query: (request) => ({
                url: `${request.workspaceId}/responder-groups/${request.groupId}/emails`,
                method: 'PATCH',
                body: request.emails
            })
        })
    })
});

export const {
    useDeleteWorkspaceDomainMutation,
    useGetSingleFormFromProviderQuery,
    useLazyGetSingleFormFromProviderQuery,
    useGetMinifiedFormsQuery,
    useLazyGetMinifiedFormsQuery,
    useImportFormMutation,
    useGetWorkspaceQuery,
    useLazyGetWorkspaceQuery,
    useGetWorkspaceFormsQuery,
    useGetWorkspaceFormQuery,
    useGetWorkspaceStatsQuery,
    useLazyGetWorkspaceFormsQuery,
    useGetWorkspaceSubmissionsQuery,
    useGetWorkspaceAllSubmissionsQuery,
    useGetWorkspaceRespondersQuery,
    useGetWorkspaceSubmissionQuery,
    useLazyGetWorkspaceSubmissionQuery,
    useSearchWorkspaceFormsMutation,
    useGetFormsSubmissionsQuery,
    usePatchFormSettingsMutation,
    useDeleteFormMutation,
    useCreateWorkspaceMutation,
    usePatchExistingWorkspaceMutation,
    usePatchThemeMutation,
    usePatchWorkspacePoliciesMutation,
    useGetAllMineWorkspacesQuery,
    useLazyGetAllMineWorkspacesQuery,
    useRequestWorkspaceSubmissionDeletionMutation,
    useCreateRespondersGroupMutation,
    useGetRespondersGroupQuery,
    useGetAllRespondersGroupQuery,
    useDeleteResponderGroupMutation,
    useUpdateResponderGroupEmailsQuery
} = workspacesApi;
