import React from 'react';

import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import MetricCard from './metric-card';

const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hrs > 0) {
        return `${hrs}h ${mins}m ${secs}s`;
    } else if (mins > 0) {
        return `${mins}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
};

interface MetricsProps {
    analyticsData: {
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
    };
}

const Metrics: React.FC<MetricsProps> = ({ analyticsData }) => {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    return (
        <div className="grid grid-cols-2 gap-6 md:grid-cols-3 lg:grid-cols-5">
            <MetricCard title={t('ANALYTICS.METRIC.VIEWS')} value={analyticsData.currentViews.toLocaleString(locale)} percentage={analyticsData.percentViews.toFixed(2)} />
            <MetricCard title={t('ANALYTICS.METRIC.VISITS')} value={analyticsData.currentVisits.toLocaleString(locale)} percentage={analyticsData.percentVisits.toFixed(2)} />
            <MetricCard title={t('ANALYTICS.METRIC.VISITORS')} value={analyticsData.currentVisitors.toLocaleString(locale)} percentage={analyticsData.percentVisitors.toFixed(2)} />
            <MetricCard title={t('ANALYTICS.METRIC.BOUNCE_RATE')} value={`${analyticsData.currentBounceRate.toFixed(2)}%`} percentage={analyticsData.percentBounceRate.toFixed(2)} />
            <MetricCard title={t('ANALYTICS.METRIC.VISIT_DURATION')} value={formatDuration(analyticsData.currentVisitDuration)} percentage={analyticsData.percentVisitDuration.toFixed(2)} />
        </div>
    );
};

export default Metrics;
