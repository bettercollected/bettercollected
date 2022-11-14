import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const OTP_API_REDUCER_KEY = 'otpApi';

const OTP_TAG_TYPES = 'OTP';
export const otpApi = createApi({
    reducerPath: OTP_API_REDUCER_KEY,
    tagTypes: [OTP_TAG_TYPES],
    baseQuery: fetchBaseQuery({
        baseUrl: `http://localhost:8000`
    }),
    endpoints: (builder) => ({
        postAuthEmail: builder.mutation<string, {}>({
            query: (body) => ({
                url: `/auth/send_code`,
                method: 'POST',
                headers: {
                    'content-type': 'application/json',
                    accept: 'application/json'
                },
                body
            }),
            invalidatesTags: [OTP_TAG_TYPES]
        })
    })
});

export const { usePostAuthEmailMutation } = otpApi;
