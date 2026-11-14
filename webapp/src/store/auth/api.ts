import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { UserStatus } from '@app/models/dtos/user-status';

import { AUTH_MFA_TAG, AUTH_OTP_TAGS, AUTH_REFRESH_TAG, AUTH_SESSIONS_TAG, AUTH_TAG_TYPES, AuthSession, MfaStatus, TotpEnrolment, VerifyOtp } from './types';

export const AUTH_REDUCER_PATH = 'authApi';
export const authApi = createApi({
    reducerPath: AUTH_REDUCER_PATH,
    tagTypes: [AUTH_TAG_TYPES, AUTH_OTP_TAGS, AUTH_REFRESH_TAG, AUTH_SESSIONS_TAG, AUTH_MFA_TAG],
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
        // `locale`: the code mail's language ("en" or "nl"; English when unset)
        // `headers`: the spam check's proof (utils/captcha/mail-proof), only when the server asks for one
        postSendOtp: builder.mutation<any, { workspace_id?: string; receiver_email: string; locale?: string; headers?: Record<string, string> }>({
            query: (body) => ({
                url: body.workspace_id ? `/workspaces/${body.workspace_id}/auth/otp/send` : `/auth/creator/otp/send`,
                method: 'POST',
                params: { receiver_email: body.receiver_email, ...(body.locale ? { locale: body.locale } : {}) },
                ...(body.headers ? { headers: body.headers } : {})
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
        // The authenticator-app second factor (/auth/mfa/*). Secrets and recovery codes
        // are only in the answers of enrol/confirm/recovery-codes: nothing here caches
        // them (keepUnusedDataFor is 0) and no tag provides them.
        getMfaStatus: builder.query<MfaStatus, void>({
            query: () => ({ url: '/auth/mfa/status', method: 'GET' }),
            providesTags: [AUTH_MFA_TAG]
        }),
        startTotpEnrolment: builder.mutation<TotpEnrolment, { code?: string } | void>({
            query: (body) => ({ url: '/auth/mfa/totp/enrol', method: 'POST', body: body ?? {} })
        }),
        confirmTotpEnrolment: builder.mutation<{ recoveryCodes: string[] }, { factorId: string; code: string }>({
            query: (body) => ({ url: '/auth/mfa/totp/confirm', method: 'POST', body }),
            invalidatesTags: [AUTH_MFA_TAG, AUTH_SESSIONS_TAG]
        }),
        regenerateRecoveryCodes: builder.mutation<{ recoveryCodes: string[] }, { code: string }>({
            query: (body) => ({ url: '/auth/mfa/recovery-codes', method: 'POST', body }),
            invalidatesTags: [AUTH_MFA_TAG]
        }),
        disableTotp: builder.mutation<MfaStatus, { code: string }>({
            query: (body) => ({ url: '/auth/mfa/totp/disable', method: 'POST', body }),
            invalidatesTags: [AUTH_MFA_TAG, AUTH_SESSIONS_TAG]
        }),
        // present the second factor in the session that is already signed in (what a workspace that requires one asks for)
        verifyMfa: builder.mutation<MfaStatus, { code: string }>({
            query: (body) => ({ url: '/auth/mfa/verify', method: 'POST', body }),
            invalidatesTags: [AUTH_MFA_TAG]
        }),
        // the second step of a sign-in: the challenge cookie and a code (or a recovery code)
        postMfaChallenge: builder.mutation<{ loggedIn: boolean; recoveryLeft?: number | null }, { code: string }>({
            query: (body) => ({ url: '/auth/mfa/challenge', method: 'POST', body })
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
    useRevokeOtherSessionsMutation,
    useGetMfaStatusQuery,
    useStartTotpEnrolmentMutation,
    useConfirmTotpEnrolmentMutation,
    useRegenerateRecoveryCodesMutation,
    useDisableTotpMutation,
    useVerifyMfaMutation,
    usePostMfaChallengeMutation
} = authApi;
