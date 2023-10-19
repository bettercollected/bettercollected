import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { IFormTemplateDto } from '@app/models/dtos/template';

import { ICreateFormFromTemplate, ICreateTemplateFromForm, IGetTemplate } from './types';

const TEMPLATE_REDUCER_PATH = 'templateApi';

const FORM_TEMPLATE = 'FORM_TEMPLATE';

export const templateApi = createApi({
    reducerPath: TEMPLATE_REDUCER_PATH,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    tagTypes: ['FORM_TEMPLATE'],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include',
        prepareHeaders: (headers) => {
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getTemplates: builder.query<Array<IFormTemplateDto>, any>({
            query: (data) => ({
                url: `/templates`,
                method: 'GET',
                params: {
                    workspace_id: data ? data : ''
                }
            }),
            providesTags: [FORM_TEMPLATE]
        }),
        getTemplateById: builder.query<IFormTemplateDto, IGetTemplate>({
            query: (data: IGetTemplate) => ({
                url: `/templates/${data.template_id}`,
                method: 'GET',
                params: {
                    workspace_id: data.workspace_id ? data.workspace_id : ''
                }
            }),
            providesTags: [FORM_TEMPLATE]
        }),
        createTemplateFromForm: builder.mutation<IFormTemplateDto, ICreateTemplateFromForm>({
            query: (data: ICreateTemplateFromForm) => ({
                url: `/workspaces/${data.workspace_id}/form/${data.form_id}/template`,
                method: 'POST'
            }),
            invalidatesTags: [FORM_TEMPLATE]
        }),
        createFormFromTemplate: builder.mutation<IFormTemplateDto, ICreateFormFromTemplate>({
            query: (data: ICreateFormFromTemplate) => ({
                url: `/workspaces/${data.workspace_id}/template/${data.template_id}`,
                method: 'POST'
            }),
            invalidatesTags: [FORM_TEMPLATE]
        }),
        createTemplate: builder.mutation<IFormTemplateDto, any>({
            query: (data) => ({
                url: `/workspaces/${data.workspace_id}/template`,
                method: 'POST',
                body: data.body
            }),
            invalidatesTags: [FORM_TEMPLATE]
        }),
        deleteTemplate: builder.mutation<string, ICreateFormFromTemplate>({
            query: (data) => ({
                url: `/workspaces/${data.workspace_id}/template/${data.template_id}`,
                method: 'DELETE'
            }),
            invalidatesTags: [FORM_TEMPLATE]
        }),
        patchTemplate: builder.mutation<IFormTemplateDto, any>({
            query: (data) => ({
                url: `/workspaces/${data.workspace_id}/template/${data.template_id}`,
                method: 'PATCH',
                body: data.body
            }),
            invalidatesTags: [FORM_TEMPLATE]
        }),
        patchTemplateSettings: builder.mutation<IFormTemplateDto, any>({
            query: (data) => ({
                url: `/workspaces/${data.workspace_id}/template/${data.template_id}/settings`,
                method: 'PATCH',
                body: data.body
            }),
            invalidatesTags: [FORM_TEMPLATE]
        }),
        importTemplate: builder.mutation<IFormTemplateDto, ICreateFormFromTemplate>({
            query: (data) => ({
                url: `/workspaces/${data.workspace_id}/template/${data.template_id}/import`,
                method: 'POST'
            }),
            invalidatesTags: [FORM_TEMPLATE]
        })
    })
});

export const {
    useGetTemplatesQuery,
    useGetTemplateByIdQuery,
    useCreateTemplateMutation,
    useCreateTemplateFromFormMutation,
    useDeleteTemplateMutation,
    useImportTemplateMutation,
    useCreateFormFromTemplateMutation,
    usePatchTemplateMutation,
    usePatchTemplateSettingsMutation
} = templateApi;
