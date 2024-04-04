import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import {
    ICreateFormFromTemplate,
    ICreateTemplateFromForm,
    IFormTemplateDto
} from '@app/store/redux/types';


const FORM_TEMPLATE = 'FORM_TEMPLATE';

export const templatesApi = createApi({
    reducerPath: 'templatesApi',
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set(
                'Access-Control-Allow-Origin',
                environments.API_ENDPOINT_HOST || ''
            );
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getTemplates: builder.query<Array<IFormTemplateDto>, any>({
            query: (data) => {
                const params: any = {};
                if (data?.workspace_id) {
                    params.workspace_id = data.workspace_id;
                }
                if (data?.v2) {
                    params.v2 = data.v2;
                }
                return {
                    url: `/templates`,
                    method: 'GET',
                    params: params
                };
            }
        }),
        createFormFromTemplate: builder.mutation<
            IFormTemplateDto,
            ICreateFormFromTemplate
        >({
            query: (data: ICreateFormFromTemplate) => ({
                url: `/workspaces/${data.workspace_id}/template/${data.template_id}`,
                method: 'POST'
            })
        }),
        createTemplateFromForm: builder.mutation<
            IFormTemplateDto,
            ICreateTemplateFromForm
        >({
            query: (data: ICreateTemplateFromForm) => ({
                url: `/workspaces/${data.workspace_id}/form/${data.form_id}/template`,
                method: 'POST'
            })
        })
    })
});

export const {
    useCreateTemplateFromFormMutation,
    useGetTemplatesQuery,
    useCreateFormFromTemplateMutation
} = templatesApi;
