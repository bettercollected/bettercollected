import React from 'react';
import MetricCard from './MetricCard';

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
    return (
        <div className="grid grid-cols-2 gap-6 md:grid-cols-3 lg:grid-cols-5">
            <MetricCard title="Views" value={analyticsData.currentViews.toLocaleString()} percentage={analyticsData.percentViews.toFixed(2)} />
            <MetricCard title="Visits" value={analyticsData.currentVisits.toLocaleString()} percentage={analyticsData.percentVisits.toFixed(2)} />
            <MetricCard title="Visitors" value={analyticsData.currentVisitors.toLocaleString()} percentage={analyticsData.percentVisitors.toFixed(2)} />
            <MetricCard title="Bounce rate" value={`${analyticsData.currentBounceRate.toFixed(2)}%`} percentage={analyticsData.percentBounceRate.toFixed(2)} />
            <MetricCard title="Visit duration" value={formatDuration(analyticsData.currentVisitDuration)} percentage={analyticsData.percentVisitDuration.toFixed(2)} />
        </div>
    );
};

export default Metrics;
