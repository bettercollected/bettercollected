import { describe, expect, it } from 'vitest';

import { formatCount, formatShare, formatWeekLabel, providerName, sortBreakdown, toWeeklySeries } from './platform-metrics';

const week = (weekStart: string, newUsers: number | null, responses = 0) => ({ weekStart, newUsers, newOrganizations: 1, newForms: 2, responses });

describe('formatCount', () => {
    it('groups thousands and rounds', () => {
        expect(formatCount(0)).toBe('0');
        expect(formatCount(999)).toBe('999');
        expect(formatCount(44004)).toBe('44,004');
        expect(formatCount(1234567.4)).toBe('1,234,567');
    });

    it('shows a dash for a missing value', () => {
        expect(formatCount(null)).toBe('—');
        expect(formatCount(undefined)).toBe('—');
        expect(formatCount(Number.NaN)).toBe('—');
    });
});

describe('formatShare', () => {
    it('is a whole percentage of the total', () => {
        expect(formatShare(1918, 2612)).toBe('73%');
        expect(formatShare(0, 10)).toBe('0%');
        expect(formatShare(8, 2612)).toBe('<1%');
    });

    it('has no share of nothing', () => {
        expect(formatShare(3, 0)).toBe('—');
    });
});

describe('formatWeekLabel', () => {
    it('reads the date as a calendar day, whatever the time zone', () => {
        expect(formatWeekLabel('2026-09-28')).toBe('28 Sep');
        expect(formatWeekLabel('2026-01-05')).toBe('5 Jan');
    });

    it('leaves an unexpected value as it is', () => {
        expect(formatWeekLabel('soon')).toBe('soon');
    });
});

describe('toWeeklySeries', () => {
    it('orders weeks oldest first and totals them', () => {
        const series = toWeeklySeries([week('2026-09-28', 3, 10), week('2026-09-21', 1, 5)], 'responses');
        expect(series.labels).toEqual(['21 Sep', '28 Sep']);
        expect(series.values).toEqual([5, 10]);
        expect(series.total).toBe(15);
        expect(series.available).toBe(true);
    });

    it('marks a series without any value as unavailable', () => {
        const series = toWeeklySeries([week('2026-09-21', null), week('2026-09-28', null)], 'newUsers');
        expect(series.values).toEqual([null, null]);
        expect(series.available).toBe(false);
        expect(series.total).toBe(0);
    });

    it('copes with no data', () => {
        expect(toWeeklySeries(undefined, 'newForms')).toEqual({ labels: [], values: [], available: false, total: 0 });
    });
});

describe('providerName', () => {
    it('names the known providers and capitalises the rest', () => {
        expect(providerName('self')).toBe('BetterCollected');
        expect(providerName('google')).toBe('Google Forms');
        expect(providerName('jotform')).toBe('Jotform');
    });
});

describe('sortBreakdown', () => {
    it('puts the largest first, ties by name', () => {
        expect(sortBreakdown({ google: 603, self: 2001, typeform: 8, aaa: 8 })).toEqual([
            ['self', 2001],
            ['google', 603],
            ['aaa', 8],
            ['typeform', 8]
        ]);
        expect(sortBreakdown(undefined)).toEqual([]);
    });
});
