import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { UserStatus } from '@app/models/dtos/UserStatus';

import { AUTH_OTP_TAGS, AUTH_REFRESH_TAG, AUTH_TAG_TYPES, VerifyOtp } from './types';

export const AUTH_REDUCER_PATH = 'authApi';
export const authApi = createApi({
    reducerPath: AUTH_REDUCER_PATH,
    tagTypes: [AUTH_TAG_TYPES, AUTH_OTP_TAGS, AUTH_REFRESH_TAG],
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
        getStatus: builder.query<UserStatus, void>({
            query: () => ({
                url: `/auth/status`,
                method: 'GET'
            }),
            providesTags: [AUTH_REFRESH_TAG]
        }),
        refreshToken: builder.mutation<any, void>({
            query: () => ({
                url: `/auth/refresh`,
                method: 'POST'
            }),
            invalidatesTags: [AUTH_REFRESH_TAG]
        }),
        postSendOtp: builder.mutation<any, { workspace_id?: string; receiver_email: string }>({
            query: (body) => ({
                url: body.workspace_id ? `/workspaces/${body.workspace_id}/auth/otp/send` : `/auth/otp/send`,
                method: 'POST',
                params: { receiver_email: body.receiver_email }
            }),
            invalidatesTags: [AUTH_OTP_TAGS]
        }),
        postSendOtpForCreator: builder.mutation<any, { receiver_email: string }>({
            query: (body) => ({
                url: `/auth/creator/otp/send`,
                method: 'POST',
                params: { receiver_email: body.receiver_email }
            }),
            invalidatesTags: [AUTH_OTP_TAGS]
        }),
        postVerifyOtp: builder.mutation<any, VerifyOtp>({
            query: (data) => ({
                url: '/auth/otp/validate',
                method: 'POST',
                body: data.body,
                params: data.params
            }),
            invalidatesTags: [AUTH_OTP_TAGS]
        }),
        logout: builder.mutation<any, void>({
            query: () => ({
                url: `/auth/logout`,
                method: 'GET'
            }),
            invalidatesTags: [AUTH_REFRESH_TAG]
        }),
        deleteAccount: builder.mutation<string, any>({
            query: (body) => ({
                url: '/auth/user/delete/workflow',
                method: 'POST',
                body: body
            })
        })
    })
});

export const { useGetStatusQuery, useDeleteAccountMutation, useLazyGetStatusQuery, usePostSendOtpMutation, usePostSendOtpForCreatorMutation, usePostVerifyOtpMutation, useLogoutMutation, useRefreshTokenMutation } = authApi;
