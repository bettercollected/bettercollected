import React, { useState, useEffect } from 'react';
import Metrics from '@Components/analytics/Metrics';
import DataTable from '@Components/analytics/DataTable';
import TimeRangeSelector from '@Components/analytics/timeRange';
import { useAppSelector } from '@app/store/hooks';
import { selectForm } from '@app/store/forms/slice';
import BarChart from '@Components/analytics/BarChart';
import { useFormAnalyticsData } from '@app/store/analytics/analyticsHook';
import EmptyResponseIcon from '@app/views/atoms/Icons/EmptyResponseIcon';

export default function FormAnalytics() {
    interface Metric {
        x: string;
        y: number;
    }

    interface AnalyticsData {
        currentViews: number;
        currentVisits: number;
        currentVisitors: number;
        currentBounceRate: number;
        currentVisitDuration: number;
        percentViews: number;
        percentVisits: number;
        percentVisitors: number;
        percentBounceRate: number;
        percentVisitDuration: number;
        detailedData: {
            referrers: Metric[];
            browsers: Metric[];
            os: Metric[];
            devices: Metric[];
            countries: Metric[];
        };
    }

    const form = useAppSelector(selectForm);
    const workspace = useAppSelector((state) => state.workspace);
    const workspaceId = workspace.workspaceName;
    const formId = form.formId;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    const [startAt, setStartAt] = useState<number>(Date.now() - 24 * 60 * 60 * 1000);
    const [endAt, setEndAt] = useState<number>(Date.now());
    const [unit, setUnit] = useState<string>('hour');
    const [range, setRange] = useState<string>('Last 24 hours');
    const [loading, setLoading] = useState<boolean>(true);

    const handleRangeSelect = (selectedRange: string) => {
        let startDate = Date.now();
        let endDate = Date.now();
        let unit = 'hour';

        switch (selectedRange) {
            case 'Today':
                startDate = new Date().setHours(0, 0, 0, 0);
                unit = 'hour';
                break;
            case 'Last 24 hours':
                startDate = Date.now() - 24 * 60 * 60 * 1000;
                unit = 'hour';
                break;
            case 'This week':
                const today = new Date();
                const dayOfWeek = today.getDay();
                startDate = new Date(today.setDate(today.getDate() - dayOfWeek)).setHours(0, 0, 0, 0);
                unit = 'day';
                break;
            case 'Last 7 days':
                startDate = Date.now() - 6 * 24 * 60 * 60 * 1000;
                unit = 'day';
                break;
            case 'This month':
                startDate = new Date(new Date().getFullYear(), new Date().getMonth(), 1).getTime();
                unit = 'day';
                break;
            case 'Last 30 days':
                startDate = Date.now() - 30 * 24 * 60 * 60 * 1000;
                unit = 'day';
                break;
            case 'Last 90 days':
                startDate = Date.now() - 90 * 24 * 60 * 60 * 1000;
                unit = 'day';
                break;
            case 'This year':
                startDate = new Date(new Date().getFullYear(), 0, 1).getTime();
                unit = 'month';
                break;
            case 'Last 6 months':
                startDate = Date.now() - 6 * 30 * 24 * 60 * 60 * 1000;
                unit = 'month';
                break;
            case 'Last 12 months':
                startDate = Date.now() - 12 * 30 * 24 * 60 * 60 * 1000;
                unit = 'month';
                break;
            case 'All time':
                startDate = 946707300000;
                unit = 'year';
                break;
            default:
                break;
        }
        setStartAt(startDate);
        setEndAt(endDate);
        setUnit(unit);
        setRange(selectedRange);
        setLoading(false);
    };

    const {
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
        pageviewsLoading,
        pageviewsError
    } = useFormAnalyticsData(workspaceId, formId, startAt, endAt, unit, timezone);

    const [analyticsData, setAnalyticsData] = useState<AnalyticsData>({
        currentViews: 0,
        currentVisits: 0,
        currentVisitors: 0,
        currentBounceRate: 0,
        currentVisitDuration: 0,
        percentViews: 0,
        percentVisits: 0,
        percentVisitors: 0,
        percentBounceRate: 0,
        percentVisitDuration: 0,
        detailedData: {
            referrers: [],
            browsers: [],
            os: [],
            devices: [],
            countries: []
        }
    });

    useEffect(() => {
        if (formStats) {
            const prevViews = formStats.pageviews?.prev || 0;
            const prevVisits = formStats.visits?.prev || 0;
            const prevVisitors = formStats.visitors?.prev || 0;
            const prevBounceRate = formStats.bounces?.prev && formStats.visits?.prev ? (formStats.bounces.prev / formStats.visits.prev) * 100 : 0;
            const prevVisitDuration = formStats.totaltime?.prev || 0;

            const currentViews = formStats.pageviews?.value || 0;
            const currentVisits = formStats.visits?.value || 0;
            const currentVisitors = formStats.visitors?.value || 0;
            const currentBounceRate = formStats.bounces?.value && formStats.visits?.value ? (formStats.bounces.value / formStats.visits.value) * 100 : 0;
            const currentVisitDuration = formStats.totaltime?.value || 0;

            setAnalyticsData((prev) => ({
                ...prev,
                currentViews: currentViews,
                currentVisits: currentVisits,
                currentVisitors: currentVisitors,
                currentBounceRate: currentBounceRate,
                currentVisitDuration: currentVisitDuration,
                percentViews: prevViews ? ((currentViews - prevViews) / prevViews) * 100 : 0,
                percentVisits: prevVisits ? ((currentVisits - prevVisits) / prevVisits) * 100 : 0,
                percentVisitors: prevVisitors ? ((currentVisitors - prevVisitors) / prevVisitors) * 100 : 0,
                percentBounceRate: prevBounceRate ? ((currentBounceRate - prevBounceRate) / prevBounceRate) * 100 : 0,
                percentVisitDuration: prevVisitDuration ? ((currentVisitDuration - prevVisitDuration) / prevVisitDuration) * 100 : 0
            }));
        }
    }, [formStats]);
    useEffect(() => {
        const referrersData = Array.isArray(referrerMetrics) ? referrerMetrics.map((item: Metric) => ({ x: item.x, y: item.y })) : [];
        const browsersData = Array.isArray(browsersMetrics) ? browsersMetrics.map((item: Metric) => ({ x: item.x, y: item.y })) : [];
        const countryData = Array.isArray(countryMetrics) ? countryMetrics.map((item: Metric) => ({ x: item.x, y: item.y })) : [];
        const osData = Array.isArray(osMetrics) ? osMetrics.map((item: Metric) => ({ x: item.x, y: item.y })) : [];
        const deviceData = Array.isArray(deviceMetrics) ? deviceMetrics.map((item: Metric) => ({ x: item.x, y: item.y })) : [];

        setAnalyticsData((prev) => ({
            ...prev,
            detailedData: {
                referrers: referrersData,
                browsers: browsersData,
                os: osData,
                devices: deviceData,
                countries: countryData
            }
        }));
    }, [referrerMetrics, browsersMetrics, osMetrics, deviceMetrics, countryMetrics]);

    const hasError = statsError || browsersMetricsError || referrerMetricsError || osMetricsError || deviceMetricsError || countryMetricsError || pageviewsError;
    const zeroViews = analyticsData.currentViews === 0;

    useEffect(() => {
        if (!statsLoading && !browsersMetricsLoading && !referrerMetricsLoading && !osMetricsLoading && !deviceMetricsLoading && !countryMetricsLoading && !pageviewsLoading) {
            setLoading(false);
        }
        if (hasError) {
            setLoading(false);
        }
    }, [statsLoading, browsersMetricsLoading, referrerMetricsLoading, osMetricsLoading, deviceMetricsLoading, countryMetricsLoading, pageviewsLoading, analyticsData, hasError]);

    if (loading) {
        return (
            <div className="mt-16 flex h-screen items-start justify-center">
                <div className="text-center">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-b-2 border-t-2 border-blue-500"></div>
                    <div className="text-sm font-medium">Loading Data...</div>
                </div>
            </div>
        );
    }

    if (hasError) {
        return (
            <>
                <TimeRangeSelector onRangeSelect={handleRangeSelect} />
                <EmptyDataResponseComponent title="No data yet" detail="There was an error while fetching the data" />
            </>
        );
    }

    if (zeroViews) {
        return (
            <>
                <TimeRangeSelector onRangeSelect={handleRangeSelect} />
                <EmptyDataResponseComponent title="No views yet" detail="There is no view in this time range." />
            </>
        );
    }

    return (
        <main>
            <TimeRangeSelector onRangeSelect={handleRangeSelect} />
            <Metrics analyticsData={analyticsData} />
            <BarChart workspaceId={workspaceId} formId={formId} startAt={startAt} endAt={endAt} unit={unit} timezone={timezone} range={range} />
            <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
                <DataTable title="Referrers" data={analyticsData.detailedData.referrers} />
                <DataTable title="Browsers" data={analyticsData.detailedData.browsers} />
                <DataTable title="Operating System" data={analyticsData.detailedData.os} />
                <DataTable title="Devices" data={analyticsData.detailedData.devices} />
                <DataTable title="Countries" data={analyticsData.detailedData.countries} showCountryFlag={true} />
            </div>
        </main>
    );
}

const EmptyDataResponseComponent = ({ title, detail }: { title: JSX.Element | string; detail: string }) => {
    return (
        <div className={'flex flex-col items-center gap-2 pl-80'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>{title}</span>
            <span className={'p4-new text-black-600'}>{detail}</span>
        </div>
    );
};
