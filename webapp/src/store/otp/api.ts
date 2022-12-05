import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const OTP_API_REDUCER_KEY = 'otpApi';

interface verifyOtp {
    email: string;
    otp_code: string;
}

const OTP_TAG_TYPES = 'OTP';
export const otpApi = createApi({
    reducerPath: OTP_API_REDUCER_KEY,
    tagTypes: [OTP_TAG_TYPES],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders: (headers, { getState }) => {
            headers.set('Access-Control-Allow-origin', 'http://localhost:8000');
            return headers;
        }
    }),
    endpoints: (builder) => ({
        postAuthEmail: builder.mutation<any, { receiver_email: string }>({
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
