import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const OTP_API_REDUCER_KEY = 'otpApi';

interface emailResponse {
    email: string;
    message: string;
}

interface verifyOtp {
    email: string;
    otp_code: string;
}

const OTP_TAG_TYPES = 'OTP';
export const otpApi = createApi({
    reducerPath: OTP_API_REDUCER_KEY,
    tagTypes: [OTP_TAG_TYPES],
    baseQuery: fetchBaseQuery({
        baseUrl: `http://localhost:8000`
    }),
    endpoints: (builder) => ({
        postAuthEmail: builder.mutation<emailResponse, { receiver_email: string }>({
            query: (body) => ({
                url: `/auth/send_code`,
                method: 'POST',
                params: { receiver_email: body.receiver_email }
            }),
            invalidatesTags: [OTP_TAG_TYPES]
        }),
        postVerifyOtp: builder.mutation<any, verifyOtp>({
            query: (body) => ({
                url: '/auth/validate',
                method: 'POST',
                body
            })
        })
    })
});

export const { usePostAuthEmailMutation, usePostVerifyOtpMutation } = otpApi;
