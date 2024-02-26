import { createApi } from '@reduxjs/toolkit/dist/query/react';
import { fetchBaseQuery } from '@reduxjs/toolkit/query';

import environments from '@app/configs/environments';


const COUPON_REDUCER_PATH = 'couponApi';
export const couponCodeApi = createApi({
    reducerPath: COUPON_REDUCER_PATH,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST + '/coupons',
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        redeemCouponCode: builder.mutation({
            query: (request) => ({
                url: `/redeem/${request.code}`,
                method: 'POST'
            })
        })
    })
});

export const { useRedeemCouponCodeMutation } = couponCodeApi;