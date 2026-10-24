import environments from '@app/configs/environments';
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const IMPORT_FORM_REDUCER_PATH = 'importApi';

interface ImportFormQueryInterface {
    workspaceId: string;
    provider: string;

    body: {
        form: any;
        response_data_owner: string;
    };
}

export const importApi = createApi({
    reducerPath: IMPORT_FORM_REDUCER_PATH,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        // The form providers this instance offers; Google carries its import
        // mode (lib/hooks/use-google-forms-import-mode.ts).
        getProviders: builder.query<Array<{ providerName: string; importMode?: string | null }>, void>({
            query: () => ({
                url: '/providers',
                method: 'GET'
            })
        }),
        verifyFormToken: builder.mutation<any, any>({
            query: ({ provider }) => ({
                url: `/${provider}/oauth/verify`,
                method: 'GET'
            })
        }),
        importForm: builder.mutation<any, ImportFormQueryInterface>({
            query: (request) => ({
                url: `/workspaces/${request.workspaceId}/forms/import/${request.provider}`,
                method: 'POST',
                body: request.body
            })
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
                return returnValue;
            }
        })
    })
});

export const { useGetProvidersQuery, useVerifyFormTokenMutation, useLazyGetSingleFormFromProviderQuery, useImportFormMutation } = importApi;
