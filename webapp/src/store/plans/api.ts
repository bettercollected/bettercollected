import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/dist/query/react';

import environments from '@app/configs/environments';

export const PLANS_PATH = 'plans';

export const plansApi = createApi({
    reducerPath: PLANS_PATH,
    refetchOnMountOrArgChange: true,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    keepUnusedDataFor: 0,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST + '/stripe',
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getPlans: builder.query<Array<any>, void>({
            query: () => ({
                url: `/plans`,
                method: 'GET'
            }),
            transformResponse(
                baseQueryReturnValue: {
                    plans: Array<any>;
                },
                meta,
                arg
            ) {
                return baseQueryReturnValue.plans;
            }
        }),
        createCheckoutSession: builder.mutation<any, any>({
            query: (request) => ({
                url: `/session/create/checkout`,
                method: 'GET',
                body: {
                    price_id: request.priceId
                }
            })
        })
    })
});

export const { useGetPlansQuery, useCreateCheckoutSessionMutation } = plansApi;
