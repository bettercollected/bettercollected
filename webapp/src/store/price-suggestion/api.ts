import { createApi } from '@reduxjs/toolkit/query/react';
import { fetchBaseQuery } from '@reduxjs/toolkit/query';

import environments from '@app/configs/environments';
import { PriceSuggestionRequest } from '@app/store/price-suggestion/types';

export const PRICE_SUGGESTION_REDUCER_PATH = 'priceSuggestionPrice';
export const priceSuggestionApi = createApi({
    reducerPath: PRICE_SUGGESTION_REDUCER_PATH,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        suggestPriceAndUpgradeUserToPro: builder.mutation<any, PriceSuggestionRequest>({
            query: (arg) => ({
                url: '/suggest-price',
                method: 'POST',
                body: arg
            })
        })
    })
});

export const { useSuggestPriceAndUpgradeUserToProMutation } = priceSuggestionApi;
