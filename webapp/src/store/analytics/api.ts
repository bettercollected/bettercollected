import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import environments from '@app/configs/environments';
import { FormStats, FormMetric, FormPageviews } from '@app/models/dtos/analytics';

export const ANALYTICS_REDUCER_PATH = 'analyticsApi';

interface GetStatsQueryParams {
    workspaceId: string;
    slug: string;
    start_at: number;
    end_at: number;
    referrer?: string;
    title?: string;
    query?: string;
    event?: string;
    host?: string;
    os?: string;
    browser?: string;
    device?: string;
    country?: string;
    region?: string;
    city?: string;
}

interface GetPageViewsQueryParams extends GetStatsQueryParams {
    unit: string;
    timezone: string;
}

interface GetMetricsQueryParams extends GetStatsQueryParams {
    type: string;
    language?: string;
    limit?: number;
}

export const analyticsApi = createApi({
    reducerPath: ANALYTICS_REDUCER_PATH,
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST,
        prepareHeaders(headers) {
            headers.set('Access-Control-Allow-Origin', environments.API_ENDPOINT_HOST);
            return headers;
        },
        credentials: 'include'
    }),
    endpoints: (builder) => ({
        getFormStats: builder.query<FormStats, GetStatsQueryParams>({
            query: ({ workspaceId, slug, start_at, end_at, ...params }) => ({
                url: `/${workspaceId}/forms/${slug}/stats`,
                method: 'GET',
                params: { start_at, end_at, ...params }
            })
        }),
        getFormPageviews: builder.query<FormPageviews, GetPageViewsQueryParams>({
            query: ({ workspaceId, slug, start_at, end_at, unit, timezone, ...params }) => ({
                url: `/${workspaceId}/forms/${slug}/pageviews`,
                method: 'GET',
                params: { start_at, end_at, unit, timezone, ...params }
            })
        }),
        getFormMetrics: builder.query<FormMetric, GetMetricsQueryParams>({
            query: ({ workspaceId, slug, start_at, end_at, type, limit = 500, ...params }) => ({
                url: `/${workspaceId}/forms/${slug}/metrics`,
                method: 'GET',
                params: { start_at, end_at, type, limit, ...params }
            })
        })
    })
});

export const { useGetFormStatsQuery, useGetFormPageviewsQuery, useGetFormMetricsQuery } = analyticsApi;
