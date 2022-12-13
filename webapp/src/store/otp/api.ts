import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const OTP_API_REDUCER_KEY = 'otpApi';

interface VerifyOtp {
    email: string;
    otp_code: string;
}

const OTP_TAG_TYPES = 'OTP';
export const otpApi = createApi({
    reducerPath: OTP_API_REDUCER_KEY,
    tagTypes: [OTP_TAG_TYPES],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        postAuthEmail: builder.mutation<any, { receiver_email: string }>({
            query: (body) => ({
                url: `/auth/otp/send`,
                method: 'POST',
                params: { receiver_email: body.receiver_email }
            }),
            invalidatesTags: [OTP_TAG_TYPES]
        }),
        postVerifyOtp: builder.mutation<any, VerifyOtp>({
            query: (body) => ({
                url: '/auth/otp/validate',
                method: 'POST',
                body
            }),
            invalidatesTags: [OTP_TAG_TYPES]
        })
    })
});

export const { usePostAuthEmailMutation, usePostVerifyOtpMutation } = otpApi;
