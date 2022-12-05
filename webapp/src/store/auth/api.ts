import { baseApi } from '../baseApi';

// export const AUTH_TAG_TYPES = 'authApi';

export const authApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        postLogout: builder.mutation<any, void>({
            query: () => ({
                url: `/auth/logout`,
                method: 'POST'
            })
        }),
        getStatus: builder.query<any, any>({
            query: (path) => `/auth/${path}`
        })
    })
});

export const { usePostLogoutMutation, useGetStatusQuery } = authApi;
