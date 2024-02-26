import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

// Import from the correct path
import environments from '@app/configs/environments';

import { IConsentField } from './types';


const CONSENT_REDUCER_PATH = 'consentApi';

export const consentApi = createApi({
    reducerPath: CONSENT_REDUCER_PATH,
    tagTypes: ['WORKSPACE_CONSENTS'],
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
        createWorkspaceConsent: builder.mutation<void, { workspaceId: string; consent: IConsentField }>({
            query: ({ workspaceId, consent }) => ({
                url: `/${workspaceId}/consent`,
                method: 'POST',
                body: consent
            }),
            invalidatesTags: ['WORKSPACE_CONSENTS']
        }),
        getAllWorkspaceConsents: builder.query<IConsentField[], string>({
            query: (workspaceId) => ({
                url: `/${workspaceId}/consent`,
                method: 'GET'
            }),
            providesTags: ['WORKSPACE_CONSENTS']
        })
    })
});

export const { useCreateWorkspaceConsentMutation, useGetAllWorkspaceConsentsQuery } = consentApi;