import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

const OTP_TAG_TYPES = 'OTP';

export const OTP_API_REDUCER_KEY = 'otpApi';

export const otpApi = createApi({
    reducerPath: OTP_API_REDUCER_KEY,
    tagTypes: [OTP_API_REDUCER_KEY],
    baseQuery: fetchBaseQuery({
        baseUrl: `http://localhost:8000`
    }),
    endpoints: (builder) => ({
        postAuthEmail: builder.mutation<string, {}>({
            query: (body) => ({
                url: `auth/send_code`,
                method: 'POST',
                body
            })
            // invalidatesTags: [OTP_TAG_TYPES]
        })
    })
});

export const { usePostAuthEmailMutation } = otpApi;
