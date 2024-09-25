import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { useFormAnalyticsData } from '@app/store/analytics/analyticsHook';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);

const getXAxisLabel = (timestamp: string, range: string) => {
    const date = dayjs.utc(timestamp);
    switch (range) {
        case 'Last 7 days':
        case 'Last 30 days':
        case 'Last 90 days':
        case 'This month':
            return date.format('D MMM');
        case 'Last 24 hours':
        case 'Today':
            return date.format('h A');
        case 'This week':
            return date.format('dddd');
        case 'This year':
        case 'Last 6 months':
        case 'Last 12 months':
            return date.format('MMMM');
        case 'All time':
            return date.format('YYYY');
        default:
            return date.format('D MMM');
    }
};

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

interface Pageview {
    x: string;
    y: number;
}

interface FormPageviewsData {
    pageviews: Pageview[];
}

interface BarChartProps {
    workspaceId: string;
    formId: string;
    startAt: number;
    endAt: number;
    unit: string;
    timezone: string;
    range: string;
}

const BarChart: React.FC<BarChartProps> = ({ workspaceId, formId, startAt, endAt, unit, timezone, range }) => {
    const { formPageviews, pageviewsError, pageviewsLoading } = useFormAnalyticsData(workspaceId, formId, startAt, endAt, unit, timezone);

    if (pageviewsLoading) {
        return (
            <div className="mt-16 flex h-screen items-start justify-center">
                <div className="text-center">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-b-2 border-t-2 border-blue-500"></div>
                    <p className="text-lg font-semibold text-gray-600">Loading...</p>
                </div>
            </div>
        );
    }

    const pageviewsData = formPageviews as FormPageviewsData;

    const labels = pageviewsData.pageviews.map((view: Pageview) => getXAxisLabel(view.x, range));
    const dataPoints = pageviewsData.pageviews.map((view: Pageview) => view.y);

    const chartData = {
        labels: labels,
        datasets: [
            {
                label: 'Visitors',
                data: dataPoints,
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 2
            }
        ]
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
            padding: {
                top: 50,
                bottom: 0,
                left: 20,
                right: 20
            }
        },
        scales: {
            x: {
                beginAtZero: true,
                grid: {
                    display: false
                },
                ticks: {
                    padding: 30
                },
                barThickness: (context: any) => {
                    const chartWidth = context.chart.width;
                    const numLabels = labels.length;
                    const barWidth = chartWidth / (numLabels * 2);
                    return Math.max(Math.min(barWidth, 20), 20);
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.09)'
                },
                ticks: {
                    padding: 10,
                    stepSize: 1,
                    callback: function (value: any) {
                        if (Number.isInteger(value)) {
                            return value;
                        }
                    }
                }
            }
        },
        plugins: {
            legend: {
                display: true,
                position: 'bottom' as const,
                labels: {
                    boxWidth: 10
                }
            }
        }
    };

    return (
        <div className="h-full w-full p-2 sm:p-4 md:h-[500px]">
            <Bar data={chartData} options={options} />
        </div>
    );
};

export default BarChart;
