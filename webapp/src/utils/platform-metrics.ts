// Pure helpers for the platform admin metrics page (/admin/metrics).
import type { PlatformWeeklyMetrics } from '@app/store/platform-admin/api';

export type WeeklySeriesKey = 'newUsers' | 'newOrganizations' | 'newForms' | 'responses';

export const WEEKLY_SERIES: Array<{ key: WeeklySeriesKey; label: string }> = [
    { key: 'newUsers', label: 'New users' },
    { key: 'newOrganizations', label: 'New organizations' },
    { key: 'newForms', label: 'New forms' },
    { key: 'responses', label: 'Responses' }
];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** 12345 -> "12,345"; null/undefined -> "—". */
export function formatCount(value: number | null | undefined): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return '—';
    return Math.round(value)
        .toString()
        .replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** part of total as a whole percentage ("42%"); "—" when total is 0. */
export function formatShare(part: number, total: number): string {
    if (!total || !Number.isFinite(part) || !Number.isFinite(total)) return '—';
    const share = (part / total) * 100;
    // a real but tiny share must not read as none
    if (part > 0 && share < 1) return '<1%';
    return `${Math.round(share)}%`;
}

/** "2026-09-28" -> "28 Sep" (the date is a UTC calendar day, so no time zone shift). */
export function formatWeekLabel(weekStart: string): string {
    const [, month, day] = weekStart.split('-').map(Number);
    if (!month || !day) return weekStart;
    return `${day} ${MONTHS[month - 1]}`;
}

export interface WeeklySeries {
    labels: string[];
    values: Array<number | null>;
    /** false when every week is missing (e.g. user counts unavailable). */
    available: boolean;
    total: number;
}

/** One series of the weekly metrics, oldest week first, for the bar chart. */
export function toWeeklySeries(weekly: PlatformWeeklyMetrics[] | undefined, key: WeeklySeriesKey): WeeklySeries {
    const weeks = [...(weekly ?? [])].sort((a, b) => a.weekStart.localeCompare(b.weekStart));
    const values = weeks.map((week) => {
        const value = week[key];
        return value === null || value === undefined ? null : value;
    });
    return {
        labels: weeks.map((week) => formatWeekLabel(week.weekStart)),
        values,
        available: values.some((value) => value !== null),
        total: values.reduce<number>((sum, value) => sum + (value ?? 0), 0)
    };
}

const PROVIDER_NAMES: Record<string, string> = {
    self: 'BetterCollected',
    google: 'Google Forms',
    typeform: 'Typeform',
    unknown: 'Unknown'
};

export function providerName(provider: string): string {
    return PROVIDER_NAMES[provider] ?? provider.charAt(0).toUpperCase() + provider.slice(1);
}

/** Largest first, ties by name — a stable order for breakdown lists. */
export function sortBreakdown(counts: Record<string, number> | undefined): Array<[string, number]> {
    return Object.entries(counts ?? {}).sort(([nameA, a], [nameB, b]) => b - a || nameA.localeCompare(nameB));
}
