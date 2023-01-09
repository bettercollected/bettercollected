import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/dist/query/react';

import environments from '@app/configs/environments';
import { workspacesApi } from '@app/store/workspaces/api';

import { AUTH_OTP_TAGS, AUTH_TAG_TYPES, VerifyOtp } from './types';

export const AUTH_REDUCER_PATH = 'authApi';
export const authApi = createApi({
    reducerPath: AUTH_REDUCER_PATH,
    tagTypes: [AUTH_TAG_TYPES, AUTH_OTP_TAGS],
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
        getStatus: builder.query<any, string>({
            query: (status) => ({
                url: `/auth/${status}`,
                method: 'GET'
            })
        }),
        postSendOtp: builder.mutation<any, { workspace_id?: string; receiver_email: string }>({
            query: (body) => ({
                url: body.workspace_id ? `/workspaces/${body.workspace_id}/auth/otp/send` : `/auth/otp/send`,
                method: 'POST',
                params: { receiver_email: body.receiver_email }
            }),
            invalidatesTags: [AUTH_OTP_TAGS]
        }),
        postVerifyOtp: builder.mutation<any, VerifyOtp>({
            query: (body) => ({
                url: '/auth/otp/validate',
                method: 'POST',
                body
            }),
            invalidatesTags: [AUTH_OTP_TAGS]
        }),
        getLogout: builder.query<any, void>({
            query: () => ({
                url: `/auth/logout`,
                method: 'GET'
            })
        })
    })
});

export const { useGetStatusQuery, useLazyGetStatusQuery, usePostSendOtpMutation, usePostVerifyOtpMutation, useLazyGetLogoutQuery } = authApi;
