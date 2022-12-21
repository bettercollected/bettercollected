import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { IGenericAPIResponse } from '@app/models/dtos/genericResponse';
import { GoogleFormDto, GoogleMinifiedFormDto } from '@app/models/dtos/googleForm';

export const FORM_API = 'googleApi';
export const FORM_TAG = 'FORM_TAG';
export const IMPORT_GOOGLE_FORMS = 'IMPORT_GOOGLE_FORMS';

interface ImportFormQueryInterface {
    form: GoogleFormDto;
    response_data_owner: string;
}

export const formsApi = createApi({
    reducerPath: FORM_API,
    tagTypes: [FORM_TAG, IMPORT_GOOGLE_FORMS],
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
        getMinifiedForms: builder.query<IGenericAPIResponse<Array<GoogleMinifiedFormDto>>, void>({
            query: () => ({
                url: 'forms/import',
                method: 'GET'
            })
        }),
        getGoogleForm: builder.query<IGenericAPIResponse<GoogleFormDto>, string>({
            query: (id) => ({
                url: `forms/import/${id}`,
                method: 'GET'
            })
        }),
        importForm: builder.mutation<any, ImportFormQueryInterface>({
            query: (body) => ({
                url: `workspaces/${environments.WORKSPACE_ID}/forms/import`,
                method: 'POST',
                body
            }),
            invalidatesTags: [IMPORT_GOOGLE_FORMS]
        })
    })
});

export const { useGetMinifiedFormsQuery, useLazyGetGoogleFormQuery, useImportFormMutation } = formsApi;
