import { useGetFormStatsQuery, useGetFormMetricsQuery, useGetFormPageviewsQuery } from './api';

export const useFormAnalyticsData = (workspaceId: string, slug: string, startAt: number, endAt: number, unit: string, timezone: string) => {
    const {
        data: formPageviews,
        error: pageviewsError,
        isLoading: pageviewsLoading
    } = useGetFormPageviewsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt,
        unit: unit,
        timezone: timezone
    });

    const {
        data: formStats,
        error: statsError,
        isLoading: statsLoading
    } = useGetFormStatsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt
    });

    const {
        data: browsersMetrics,
        error: browsersMetricsError,
        isLoading: browsersMetricsLoading
    } = useGetFormMetricsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt,
        type: 'browser'
    });

    const {
        data: referrerMetrics,
        error: referrerMetricsError,
        isLoading: referrerMetricsLoading
    } = useGetFormMetricsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt,
        type: 'referrer'
    });

    const {
        data: deviceMetrics,
        error: deviceMetricsError,
        isLoading: deviceMetricsLoading
    } = useGetFormMetricsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt,
        type: 'device'
    });

    const {
        data: osMetrics,
        error: osMetricsError,
        isLoading: osMetricsLoading
    } = useGetFormMetricsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt,
        type: 'os'
    });

    const {
        data: countryMetrics,
        error: countryMetricsError,
        isLoading: countryMetricsLoading
    } = useGetFormMetricsQuery({
        workspaceId,
        slug,
        start_at: startAt,
        end_at: endAt,
        type: 'country'
    });

    return {
        formStats,
        statsError,
        statsLoading,
        browsersMetrics,
        browsersMetricsError,
        browsersMetricsLoading,
        referrerMetrics,
        referrerMetricsError,
        referrerMetricsLoading,
        deviceMetrics,
        deviceMetricsError,
        deviceMetricsLoading,
        osMetrics,
        osMetricsError,
        osMetricsLoading,
        countryMetrics,
        countryMetricsError,
        countryMetricsLoading,
        formPageviews,
        pageviewsError,
        pageviewsLoading
    };
};
