import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { UserStatus } from '@app/models/dtos/user-status';

import { AUTH_OTP_TAGS, AUTH_REFRESH_TAG, AUTH_SESSIONS_TAG, AUTH_TAG_TYPES, AuthSession, VerifyOtp } from './types';

export const AUTH_REDUCER_PATH = 'authApi';
export const authApi = createApi({
    reducerPath: AUTH_REDUCER_PATH,
    tagTypes: [AUTH_TAG_TYPES, AUTH_OTP_TAGS, AUTH_REFRESH_TAG, AUTH_SESSIONS_TAG],
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
                url: body.workspace_id ? `/workspaces/${body.workspace_id}/auth/otp/send` : `/auth/creator/otp/send`,
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
        getSessions: builder.query<AuthSession[], void>({
            query: () => ({
                url: '/auth/sessions',
                method: 'GET'
            }),
            providesTags: [AUTH_SESSIONS_TAG]
        }),
        revokeSession: builder.mutation<{ revoked: number }, string>({
            query: (sessionId) => ({
                url: `/auth/sessions/${encodeURIComponent(sessionId)}`,
                method: 'DELETE'
            }),
            invalidatesTags: [AUTH_SESSIONS_TAG]
        }),
        revokeOtherSessions: builder.mutation<{ revoked: number }, void>({
            query: () => ({
                url: '/auth/sessions',
                method: 'DELETE'
            }),
            invalidatesTags: [AUTH_SESSIONS_TAG]
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

export const {
    useGetStatusQuery,
    useDeleteAccountMutation,
    useLazyGetStatusQuery,
    usePostSendOtpMutation,
    usePostVerifyOtpMutation,
    useLogoutMutation,
    useRefreshTokenMutation,
    useGetSessionsQuery,
    useRevokeSessionMutation,
    useRevokeOtherSessionsMutation
} = authApi;
