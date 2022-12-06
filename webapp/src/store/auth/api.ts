import { baseApi } from '../baseApi';
import { AUTH_LOG_OUT, AUTH_TAG_TYPES } from './types';

export const authApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getLogout: builder.query<any, void>({
            query: () => ({
                url: `/auth/logout`,
                method: 'GET',
                credentials: 'include'
            }),
            providesTags: [AUTH_LOG_OUT]
        }),
        getStatus: builder.query<any, any>({
            query: (path) => ({
                url: `/auth/${path}`,
                method: 'GET',
                credentials: 'include'
            }),
            providesTags: (_) => [AUTH_TAG_TYPES]
        })
    })
});

export const { useGetLogoutQuery, useLazyGetLogoutQuery, useGetStatusQuery } = authApi;
