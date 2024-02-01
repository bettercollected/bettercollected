import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { StandardFormDto, StandardFormResponseDto, WorkspaceResponderDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { Page } from '@app/models/dtos/page';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { WorkspaceStatsDto } from '@app/models/dtos/workspaceStatsDto';
import { IGetAllSubmissionsQuery, IGetFormSubmissionsQuery, IGetWorkspaceFormQuery, IGetWorkspaceSubmissionQuery, IPatchFormSettingsRequest, ISearchWorkspaceFormsQuery } from '@app/store/workspaces/types';

export const WORKSPACES_REDUCER_PATH = 'workspacesApi';

const WORKSPACE_TAGS = 'WORKSPACE_TAG';
const SUBMISSION_TAG = 'SUBMISSION_TAG';
const WORKSPACE_UPDATE_TAG = 'WORKSPACE_UPDATE_TAG';
const GROUP_TAG = 'GROUP_TAG';
const RESPONDER_TAG = 'RESPONDER_TAG';
const FORM_TAG = 'FORM_TAG';

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
    tagTypes: [WORKSPACE_TAGS, WORKSPACE_UPDATE_TAG, SUBMISSION_TAG, GROUP_TAG, RESPONDER_TAG, FORM_TAG],
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
                method: 'GET'
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
                refetchOnMountOrArgChange: false,
                refetchOnReconnect: false,
                refetchOnFocus: false
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
        verifyFormToken: builder.mutation<any, any>({
            query: ({ provider }) => ({
                url: `/${provider}/oauth/verify`,
                method: 'GET'
            })
        }),

        publishForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/publish`,
                method: 'POST',
                body: request.body
            }),
            invalidatesTags: [FORM_TAG]
        }),
        createForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms`,
                method: 'POST',
                body: request.body
            }),
            invalidatesTags: [FORM_TAG]
        }),
        patchForm: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}`,
                method: 'PATCH',
                body: request.body
            }),
            invalidatesTags: [FORM_TAG]
        }),
        submitResponse: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/response`,
                method: 'POST',
                body: request.body
            })
        }),
        deleteResponse: builder.mutation<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/response/${request.responseId}`,
                method: 'DELETE'
            }),
            invalidatesTags: [SUBMISSION_TAG]
        }),
        importForm: builder.mutation<any, ImportFormQueryInterface>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/import/${request.provider}`,
                method: 'POST',
                body: request.body
            }),
            invalidatesTags: [WORKSPACE_TAGS]
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
        getFormsSubmissions: builder.query<Page<StandardFormResponseDto>, IGetFormSubmissionsQuery>({
            query: (query) => ({
                url: `/workspaces/${query.workspaceId}/forms/${query.formId}/submissions`,
                params: {
                    request_for_deletion: query.requestedForDeletionOly,
                    page: query.page,
                    size: query.size,
                    dataOwnerIdentifier: query.dataOwnerIdentifier
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
                url: `/workspaces/${query.workspace_id}/submissions/${query.submission_id}`,
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
        }),
        exportCSVResponses: builder.query<any, any>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/${request.formId}/export-csv`,
                method: 'GET'
            }),
            providesTags: [GROUP_TAG, RESPONDER_TAG, FORM_TAG]
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
    useCreateFormMutation,
    useGetWorkspaceSubmissionsQuery,
    useGetWorkspaceAllSubmissionsQuery,
    useGetWorkspaceRespondersQuery,
    useGetWorkspaceSubmissionQuery,
    useLazyGetWorkspaceSubmissionQuery,
    useLazyGetWorkspaceNameSuggestionsQuery,
    useLazyGetWorkspaceNameAvailabilityQuery,
    useLazySearchWorkspaceFormsQuery,
    useGetFormsSubmissionsQuery,
    usePatchFormMutation,
    useDeleteResponseMutation,
    usePatchFormSettingsMutation,
    useDeleteFormMutation,
    useSubmitResponseMutation,
    useCreateWorkspaceMutation,
    usePatchExistingWorkspaceMutation,
    usePatchThemeMutation,
    useDuplicateFormMutation,
    usePatchWorkspacePoliciesMutation,
    useGetAllMineWorkspacesQuery,
    useLazyGetAllMineWorkspacesQuery,
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
    usePublishFormMutation,
    useVerifyFormTokenMutation,
    useExportCSVResponsesQuery,
    useLazyExportCSVResponsesQuery,
    useGetWorkspaceSubmissionByUUIDQuery,
    useLazyGetWorkspaceSubmissionByUUIDQuery
} = workspacesApi;
