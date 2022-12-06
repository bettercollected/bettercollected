import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const GOOGLE_API = 'GOOGLE_API';
export const GOOGLE_API_TAG = 'GOOGLE_API_TAG';

export const googleApiSlice = createApi({
    reducerPath: GOOGLE_API,
    tagTypes: [GOOGLE_API_TAG],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include',
        prepareHeaders: (headers, { getState }) => {
            headers.set('Access-Control-Allow-origin', 'http://localhost:8000');
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getConnectToGoogle: builder.query<any, null>({
            query: () => ({
                url: `/auth/google/connect`,
                method: 'GET',
                credentials: 'include'
            })
            // invalidatesTags: [GOOGLE_API_TAG]
        })
        // postVerifyOtp: builder.mutation<any, verifyOtp>({
        //     query: (body) => ({
        //         url: '/auth/otp/validate',
        //         method: 'POST',
        //         body
        //     })
        // })
    })
});

export const { useGetConnectToGoogleQuery } = googleApiSlice;
