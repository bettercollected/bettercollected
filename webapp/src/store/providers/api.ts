import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/dist/query/react';

import environments from '@app/configs/environments';
import { IntegrationFormProviders } from '@app/models/dtos/provider';

import { PROVIDER_TAG_TYPES } from './types';

export const PROVIDER_REDUCER_PATH = 'providerApi';
export const providerApi = createApi({
    reducerPath: PROVIDER_REDUCER_PATH,
    tagTypes: [PROVIDER_TAG_TYPES],
    refetchOnReconnect: true,
    refetchOnMountOrArgChange: true,
    keepUnusedDataFor: 0,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include',
        prepareHeaders: (headers) => {
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getEnabledProviders: builder.query<Array<IntegrationFormProviders>, void>({
            query: () => ({
                url: `/providers`,
                method: 'GET'
            }),
            providesTags: [PROVIDER_TAG_TYPES]
        })
    })
});

export const { useGetEnabledProvidersQuery, useLazyGetEnabledProvidersQuery } = providerApi;
