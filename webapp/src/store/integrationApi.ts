import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {fetchBaseQuery} from '@reduxjs/toolkit/query';

import environments from '@app/configs/environments';

export const integrationApi = createApi({
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getIntegrationOauthUrl: builder.query<any, any>({
            query: ({integrationType}) => ({
                url: `/integration/${integrationType}/oauth`,
                method: 'GET',
            })
        }),
        handleIntegrationOauthCallback: builder.mutation<any, any>({
            query: (request: any) => ({
                url: `/integration/${request?.integrationType}/oauth/callback`,
                method: 'POST',
                body: request.body
            })
        })
    })
});

export const {useLazyGetIntegrationOauthUrlQuery, useHandleIntegrationOauthCallbackMutation} = integrationApi;
