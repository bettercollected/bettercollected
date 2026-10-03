'use client';

import React, { useMemo, useState } from 'react';

import Link from 'next/link';

import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js';
import { AlertTriangle, RefreshCw, ShieldAlert } from 'lucide-react';
import { Bar } from 'react-chartjs-2';

import AuthNavbar from '@app/components/auth/auth-navbar';
import { Button } from '@app/shadcn/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@app/shadcn/components/ui/card';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { PlatformMetrics, useGetPlatformMetricsQuery } from '@app/store/platform-admin/api';
import { WEEKLY_SERIES, WeeklySeriesKey, formatCount, formatShare, providerName, sortBreakdown, toWeeklySeries } from '@app/utils/platform-metrics';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

const BRAND_500 = '#2456CC';
const BRAND_600 = '#1E49AD';
const GRID = '#E9EEF5'; // black-200
const INK_MUTED = '#657085'; // black-600

interface IStat {
    label: string;
    value: number | null | undefined;
    hint?: string;
}

function StatGroup({ title, description, stats, children }: { title: string; description: string; stats: IStat[]; children?: React.ReactNode }) {
    return (
        <Card className="rounded-xl border-black-200 bg-white shadow-none">
            <CardHeader className="p-5 pb-3">
                <CardTitle className="text-base font-semibold tracking-normal text-black-900">{title}</CardTitle>
                <CardDescription className="text-xs text-black-600">{description}</CardDescription>
            </CardHeader>
            <CardContent className="p-5 pt-0">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3">
                    {stats.map((stat, index) => (
                        <div key={stat.label} className="min-w-0">
                            <dt className="truncate text-xs font-medium text-black-600">{stat.label}</dt>
                            <dd className={`mt-1 font-semibold tabular-nums text-black-900 ${index === 0 ? 'text-2xl' : 'text-xl'}`}>{formatCount(stat.value)}</dd>
                            {stat.hint && <dd className="mt-0.5 text-xs text-black-500">{stat.hint}</dd>}
                        </div>
                    ))}
                </dl>
                {children}
            </CardContent>
        </Card>
    );
}

function Breakdown({ label, counts, total, name = (key: string) => key }: { label: string; counts: Record<string, number>; total: number; name?: (key: string) => string }) {
    const rows = sortBreakdown(counts);
    if (!rows.length) return null;
    return (
        <div className="mt-4 border-t border-black-200 pt-3">
            <p className="mb-2 text-xs font-medium text-black-600">{label}</p>
            <ul className="space-y-2">
                {rows.map(([key, count]) => (
                    <li key={key} className="text-sm text-black-800">
                        <div className="flex items-baseline justify-between gap-3">
                            <span className="truncate">{name(key)}</span>
                            <span className="shrink-0 tabular-nums text-black-600">
                                {formatCount(count)} · {formatShare(count, total)}
                            </span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-black-200" aria-hidden>
                            <div className="h-full rounded-full bg-brand-500" style={{ width: total ? `${(count / total) * 100}%` : 0 }} />
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function WeeklyChart({ weekly }: { weekly: PlatformMetrics['weekly'] }) {
    // Start on the first series with data (user counts can be unavailable).
    const [seriesKey, setSeriesKey] = useState<WeeklySeriesKey>(() => WEEKLY_SERIES.find((s) => toWeeklySeries(weekly, s.key).available)?.key ?? 'newUsers');
    const series = useMemo(() => toWeeklySeries(weekly, seriesKey), [weekly, seriesKey]);
    const seriesLabel = WEEKLY_SERIES.find((s) => s.key === seriesKey)?.label ?? '';

    return (
        <Card className="rounded-xl border-black-200 bg-white shadow-none">
            <CardHeader className="flex flex-col gap-3 p-5 pb-3 md:flex-row md:items-start md:justify-between md:space-y-0">
                <div>
                    <CardTitle className="text-base font-semibold tracking-normal text-black-900">Last 12 weeks</CardTitle>
                    <CardDescription className="text-xs text-black-600">Per week, Monday to Sunday (UTC); the last bar is the current week. {series.available && `${seriesLabel}: ${formatCount(series.total)} in total.`}</CardDescription>
                </div>
                <Tabs value={seriesKey} onValueChange={(value) => setSeriesKey(value as WeeklySeriesKey)}>
                    <TabsList className="h-auto flex-wrap justify-start">
                        {WEEKLY_SERIES.map((s) => (
                            <TabsTrigger key={s.key} value={s.key} className="text-xs">
                                {s.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </Tabs>
            </CardHeader>
            <CardContent className="p-5 pt-0">
                {series.available ? (
                    <div className="h-[280px] w-full" role="img" aria-label={`${seriesLabel} per week, last 12 weeks`}>
                        <Bar
                            data={{
                                labels: series.labels,
                                datasets: [
                                    {
                                        label: seriesLabel,
                                        data: series.values,
                                        backgroundColor: BRAND_500,
                                        hoverBackgroundColor: BRAND_600,
                                        borderRadius: 4,
                                        borderSkipped: 'bottom',
                                        maxBarThickness: 28
                                    }
                                ]
                            }}
                            options={{
                                responsive: true,
                                maintainAspectRatio: false,
                                animation: false,
                                plugins: { legend: { display: false }, tooltip: { displayColors: false } },
                                scales: {
                                    x: { grid: { display: false }, ticks: { color: INK_MUTED, font: { size: 11 } } },
                                    y: {
                                        beginAtZero: true,
                                        border: { display: false },
                                        grid: { color: GRID },
                                        ticks: { color: INK_MUTED, font: { size: 11 }, precision: 0 }
                                    }
                                }
                            }}
                        />
                    </div>
                ) : (
                    <p className="flex h-[280px] items-center justify-center text-sm text-black-600">No {seriesLabel.toLowerCase()} data available.</p>
                )}
                <details className="mt-3">
                    <summary className="cursor-pointer text-xs font-medium text-black-600 hover:text-black-900">Show as table</summary>
                    <div className="mt-2 overflow-x-auto">
                        <table className="w-full text-left text-xs">
                            <thead className="text-black-600">
                                <tr>
                                    <th className="py-1 pr-3 font-medium">Week of</th>
                                    {WEEKLY_SERIES.map((s) => (
                                        <th key={s.key} className="py-1 pr-3 text-right font-medium">
                                            {s.label}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="tabular-nums text-black-800">
                                {[...weekly]
                                    .sort((a, b) => a.weekStart.localeCompare(b.weekStart))
                                    .map((week) => (
                                        <tr key={week.weekStart} className="border-t border-black-200">
                                            <td className="py-1 pr-3">{week.weekStart}</td>
                                            {WEEKLY_SERIES.map((s) => (
                                                <td key={s.key} className="py-1 pr-3 text-right">
                                                    {formatCount(week[s.key])}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                            </tbody>
                        </table>
                    </div>
                </details>
            </CardContent>
        </Card>
    );
}

function StateMessage({ icon, title, children }: { icon: React.ReactNode; title: string; children?: React.ReactNode }) {
    return (
        <div className="mx-auto mt-10 flex max-w-md flex-col items-center rounded-xl border border-black-200 bg-white p-8 text-center">
            <div className="mb-3 text-black-600">{icon}</div>
            <h2 className="text-base font-semibold text-black-900">{title}</h2>
            {children && <div className="mt-2 text-sm text-black-600">{children}</div>}
        </div>
    );
}

function LoadingGrid() {
    return (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2" aria-busy="true" aria-label="Loading metrics">
            {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-[150px] rounded-xl bg-black-200" />
            ))}
            <Skeleton className="h-[360px] rounded-xl bg-black-200 lg:col-span-2" />
        </div>
    );
}

function NotAuthorized() {
    return (
        <StateMessage icon={<ShieldAlert className="h-8 w-8" />} title="Not authorized">
            Platform metrics are only available to BetterCollected platform administrators.
        </StateMessage>
    );
}

export default function PlatformMetricsView() {
    const auth = useAppSelector(selectAuth);
    const isPlatformAdmin = !!auth?.roles?.includes('ADMIN');
    const isSignedIn = !!auth?.id;
    const { data, error, isLoading, isFetching, refetch } = useGetPlatformMetricsQuery(undefined, { skip: !isPlatformAdmin });
    const status = (error as { status?: number | string } | undefined)?.status;

    let body: React.ReactNode;
    if (auth?.isLoading) {
        body = <LoadingGrid />;
    } else if (!isSignedIn || status === 401) {
        body = (
            <StateMessage icon={<ShieldAlert className="h-8 w-8" />} title="Sign in required">
                <Link href="/login" className="font-medium text-brand-500 hover:underline">
                    Sign in
                </Link>{' '}
                with a platform administrator account to see platform metrics.
            </StateMessage>
        );
    } else if (!isPlatformAdmin || status === 403) {
        body = <NotAuthorized />;
    } else if (isLoading) {
        body = <LoadingGrid />;
    } else if (error || !data) {
        body = (
            <StateMessage icon={<AlertTriangle className="h-8 w-8" />} title="Couldn't load platform metrics">
                <p>Something went wrong while counting. Try again in a moment.</p>
                <Button variant="v2Button" className="mx-auto mt-4" onClick={() => refetch()} isLoading={isFetching}>
                    Try again
                </Button>
            </StateMessage>
        );
    } else {
        body = <MetricsGrid metrics={data} />;
    }

    return (
        <div className="min-h-screen bg-black-100">
            <AuthNavbar showPlans={false} showHamburgerIcon={false} />
            <main className="mx-auto w-full max-w-6xl px-5 pb-16 pt-[100px] lg:px-10">
                <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <h1 className="h3-new text-black-900">Platform metrics</h1>
                        <p className="mt-1 text-sm text-black-600">
                            Counts across every workspace on this instance. Aggregates only — no names, emails or answers.
                            {data?.generatedAt && <> Counted at {new Date(data.generatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}; refreshed at most once a minute.</>}
                        </p>
                    </div>
                    {isPlatformAdmin && data && (
                        <Button variant="v2Button" icon={<RefreshCw className="h-4 w-4" />} onClick={() => refetch()} isLoading={isFetching}>
                            Refresh
                        </Button>
                    )}
                </div>
                {body}
            </main>
        </div>
    );
}

function MetricsGrid({ metrics }: { metrics: PlatformMetrics }) {
    const { organizations, users, formCreators, formResponders, forms, responses } = metrics;
    const usersError = metrics.errors.find((e) => e.source === 'users');

    return (
        <div className="flex flex-col gap-5">
            {metrics.errors.length > 0 && (
                <div role="status" className="flex items-start gap-3 rounded-xl border border-[#F2D7A6] bg-[#FFF8EB] p-4 text-sm text-[#7A4B00]">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                        <p className="font-semibold">Some counts are unavailable</p>
                        <ul className="mt-1 list-disc pl-4">
                            {metrics.errors.map((e) => (
                                <li key={e.source}>{e.message}</li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <StatGroup
                    title="Users"
                    description="Accounts on this instance. Active means signed in during the last 30 days."
                    stats={[
                        { label: 'Total', value: users?.total },
                        { label: 'New, last 30 days', value: users?.newLast30Days },
                        { label: 'Active, last 30 days', value: users?.activeLast30Days }
                    ]}
                >
                    {users ? <Breakdown label="By plan" counts={users.byPlan} total={users.total} /> : <p className="mt-3 text-xs text-black-500">{usersError?.message ?? 'User counts are unavailable.'}</p>}
                </StatGroup>
                <StatGroup
                    title="Organizations"
                    description="Workspaces, including each user's default one."
                    stats={[
                        { label: 'Total', value: organizations.total },
                        { label: 'New, last 30 days', value: organizations.newLast30Days },
                        { label: 'Disabled', value: organizations.disabled }
                    ]}
                />
                <StatGroup
                    title="Form creators"
                    description="Users who created or imported at least one form that still exists."
                    stats={[
                        { label: 'Total', value: formCreators.total },
                        { label: 'Created a form, last 30 days', value: formCreators.activeLast30Days }
                    ]}
                />
                <StatGroup
                    title="Form responders"
                    description="Identified responders are distinct respondent identities; anonymous responses name nobody."
                    stats={[
                        { label: 'Identified responders', value: formResponders.identified },
                        { label: 'Anonymous responses', value: formResponders.anonymousResponses }
                    ]}
                />
                <StatGroup
                    title="Forms"
                    description="Forms in workspaces. Published means at least one version was published."
                    stats={[
                        { label: 'Total', value: forms.total },
                        { label: 'Published', value: forms.published, hint: formatShare(forms.published, forms.total) },
                        { label: 'New, last 30 days', value: forms.newLast30Days }
                    ]}
                >
                    <Breakdown label="By source" counts={forms.byProvider} total={forms.total} name={providerName} />
                </StatGroup>
                <StatGroup
                    title="Responses"
                    description="Submitted responses, dated by submission time (imported ones too)."
                    stats={[
                        { label: 'Total', value: responses.total },
                        { label: 'Last 7 days', value: responses.last7Days },
                        { label: 'Last 30 days', value: responses.last30Days }
                    ]}
                />
            </div>
            <WeeklyChart weekly={metrics.weekly} />
        </div>
    );
}
