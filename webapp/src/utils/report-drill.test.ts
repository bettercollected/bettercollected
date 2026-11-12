import { describe, expect, it } from 'vitest';

import { bucketDays, listFiltersFor } from '@app/utils/report-drill';

describe('the days a time group covers', () => {
    it('is the day itself, a week from its Monday, a month and a year', () => {
        expect(bucketDays('2026-03-09', 'day')).toEqual({ from: '2026-03-09', to: '2026-03-09' });
        expect(bucketDays('2026-03-09', 'week')).toEqual({ from: '2026-03-09', to: '2026-03-15' });
        expect(bucketDays('2026-12-28', 'week')).toEqual({ from: '2026-12-28', to: '2027-01-03' });
        expect(bucketDays('2026-02', 'month')).toEqual({ from: '2026-02-01', to: '2026-02-28' });
        expect(bucketDays('2028-02', 'month')).toEqual({ from: '2028-02-01', to: '2028-02-29' });
        expect(bucketDays('2026', 'year')).toEqual({ from: '2026-01-01', to: '2026-12-31' });
    });

    it('says nothing for a key that is no time', () => {
        expect(bucketDays('banana', 'day')).toBeUndefined();
        expect(bucketDays('2026-99-99', 'day')).toBeUndefined();
    });
});

describe('the list address of a group', () => {
    const current = { status: 'none' as const, version: 1 };

    it('narrows the list to a form version, to anonymous or identified, or to the days of a bucket, over the filters already in force', () => {
        expect(listFiltersFor({ field: 'form_version' }, '3', current, false)).toEqual({ status: 'none', version: 3 });
        expect(listFiltersFor({ field: 'respondent' }, 'known', current, false)).toEqual({ status: 'none', version: 1, who: 'known' });
        expect(listFiltersFor({ field: 'submitted_at', bucket: 'month' }, '2026-03', { from: '2026-01-01' }, false)).toEqual({ from: '2026-03-01', to: '2026-03-31' });
    });

    it('has none for a group of answers, for one the list cannot say, and for a report with conditions on answers', () => {
        expect(listFiltersFor({ field: 'q:team' }, 'north', current, false)).toBeUndefined();
        expect(listFiltersFor({ field: 'source' }, 'api', current, false)).toBeUndefined();
        expect(listFiltersFor({ field: 'form_version' }, '0', current, false)).toBeUndefined();
        expect(listFiltersFor({ field: 'respondent' }, 'someone', current, false)).toBeUndefined();
        expect(listFiltersFor({ field: 'form_version' }, '3', current, true)).toBeUndefined();
        expect(listFiltersFor(undefined, 'x', current, false)).toBeUndefined();
    });
});
