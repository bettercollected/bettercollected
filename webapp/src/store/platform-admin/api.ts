import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';

export const PLATFORM_ADMIN_REDUCER_PATH = 'platformAdminApi';

// GET /admin/metrics — platform admins only (ADMIN role), aggregates only.
export interface PlatformWeeklyMetrics {
    weekStart: string;
    /** null when the auth service could not answer. */
    newUsers: number | null;
    newOrganizations: number;
    newForms: number;
    responses: number;
}

export interface PlatformMetrics {
    generatedAt: string;
    organizations: { total: number; newLast30Days: number; disabled: number };
    /** null when the auth service could not answer (see errors). */
    users: { total: number; newLast30Days: number; activeLast30Days: number; byPlan: Record<string, number> } | null;
    formCreators: { total: number; activeLast30Days: number };
    formResponders: { identified: number; anonymousResponses: number };
    forms: { total: number; published: number; newLast30Days: number; byProvider: Record<string, number> };
    responses: { total: number; last7Days: number; last30Days: number };
    weekly: PlatformWeeklyMetrics[];
    errors: Array<{ source: string; message: string }>;
}

export const platformAdminApi = createApi({
    reducerPath: PLATFORM_ADMIN_REDUCER_PATH,
    refetchOnMountOrArgChange: true,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getPlatformMetrics: builder.query<PlatformMetrics, void>({
            query: () => ({ url: '/admin/metrics', method: 'GET' })
        })
    })
});

export const { useGetPlatformMetricsQuery } = platformAdminApi;
