import { afterEach, describe, expect, it } from 'vitest';

import { DEFAULT_STATE, activeFilterCount, hasListParams, localDayStart, nearbyPages, parseResponseListState, responseListApiParams, responseListSearchParams, responseListView } from './response-list-state';

const parse = (query: string) => parseResponseListState(new URLSearchParams(query));

describe('reading the list state from a URL', () => {
    it('is the default for a URL without parameters', () => {
        expect(parse('')).toEqual(DEFAULT_STATE);
    });

    it('reads every parameter', () => {
        expect(parse('page=3&size=50&sort=oldest&from=2026-01-05&to=2026-01-10&status=pending&who=known&version=2&cursor=abc.def-1_2')).toEqual({
            page: 3,
            size: 50,
            sort: 'oldest',
            from: '2026-01-05',
            to: '2026-01-10',
            status: 'pending',
            who: 'known',
            version: 2,
            cursor: 'abc.def-1_2'
        });
    });

    it.each([
        ['page=0', { page: 1 }],
        ['page=-4', { page: 1 }],
        ['page=abc', { page: 1 }],
        ['page=1.5', { page: 1 }],
        ['page=99999999999', { page: 1 }],
        ['size=10', { size: 25 }],
        ['size=1000', { size: 25 }],
        ['sort=price', { sort: 'newest' }],
        ['from=2026-02-30', {}],
        ['from=yesterday', {}],
        ['from=1969-12-31', {}],
        ['status=success', {}],
        ['status=pending,none', {}],
        ['who=robot', {}],
        ['version=0', {}],
        ['version=-1', {}],
        ['version=2;drop', {}],
        ["cursor='; DROP TABLE x; --", {}],
        ['cursor=' + 'a'.repeat(3000), {}]
    ])('falls back to the default for %s', (query, expected) => {
        expect(parse(query)).toEqual({ ...DEFAULT_STATE, ...expected });
    });

    it('drops an end date before the start date', () => {
        expect(parse('from=2026-03-10&to=2026-03-01')).toEqual({ ...DEFAULT_STATE, from: '2026-03-10' });
    });

    it('ignores the repeated parameters beyond the first and unknown ones', () => {
        expect(parse('page=2&page=5&utm_source=x')).toEqual({ ...DEFAULT_STATE, page: 2 });
    });
});

describe('writing the list state to a URL', () => {
    it('leaves out the defaults', () => {
        expect(responseListSearchParams(DEFAULT_STATE).toString()).toBe('');
        expect(responseListSearchParams({ ...DEFAULT_STATE, page: 1, size: 25, sort: 'newest' }).toString()).toBe('');
    });

    it('round-trips', () => {
        const state = { page: 7, size: 100 as const, sort: 'version-low' as const, from: '2026-01-05', to: '2026-02-01', status: 'none' as const, who: 'anonymous' as const, version: 3, cursor: 'tok.en' };
        expect(parse(responseListSearchParams(state).toString())).toEqual(state);
    });

    it('never holds a search text: the state has no place for one', () => {
        expect(Object.keys(parse('dataOwnerIdentifier=a@b.c&q=a@b.c'))).not.toContain('dataOwnerIdentifier');
        expect(responseListSearchParams(parse('dataOwnerIdentifier=a@b.c&q=a@b.c')).toString()).toBe('');
    });

    it('knows its own parameters and counts the filters', () => {
        expect(hasListParams(new URLSearchParams('foo=1'))).toBe(false);
        expect(hasListParams(new URLSearchParams('sort=oldest'))).toBe(true);
        expect(activeFilterCount(parse('page=3&sort=oldest&size=50'))).toBe(0);
        expect(activeFilterCount(parse('from=2026-01-05&who=known'))).toBe(2);
    });

    it('names the list without its page and cursor', () => {
        expect(responseListView(parse('page=4&cursor=abc&sort=oldest&who=known'))).toBe('sort=oldest&who=known');
    });
});

describe('asking the API', () => {
    const original = process.env.TZ;
    afterEach(() => {
        process.env.TZ = original;
    });

    it('asks for keyset paging with the sort and the filters', () => {
        const params = responseListApiParams({ ...DEFAULT_STATE, page: 3, size: 50, sort: 'version-low', status: 'pending', who: 'known', version: 2, cursor: 'tok' });
        expect(params).toMatchObject({ paging: 'keyset', page: 3, size: 50, sort_by: 'form_version', sort_order: 'ASCENDING', status: 'pending', respondent: 'known', formVersion: 2, cursor: 'tok' });
        expect(params.submittedFrom).toBeUndefined();
        expect(responseListApiParams(DEFAULT_STATE)).toMatchObject({ sort_by: 'created_at', sort_order: 'DESCENDING' });
    });

    it('sends the instants the viewer\'s days begin at: from inclusive, to = the start of the day after', () => {
        process.env.TZ = 'Europe/Amsterdam';
        const params = responseListApiParams({ ...DEFAULT_STATE, from: '2026-01-05', to: '2026-01-05' });
        // a one-day range: [Jan 5 00:00 CET, Jan 6 00:00 CET)
        expect(params.submittedFrom).toBe('2026-01-04T23:00:00.000Z');
        expect(params.submittedTo).toBe('2026-01-05T23:00:00.000Z');
    });

    it('follows the viewer\'s time zone over a daylight-saving change', () => {
        process.env.TZ = 'Europe/Amsterdam';
        // 29 March 2026 has 23 hours: clocks go forward at 02:00
        expect(localDayStart('2026-03-29')).toBe('2026-03-28T23:00:00.000Z');
        expect(localDayStart('2026-03-29', 1)).toBe('2026-03-29T22:00:00.000Z');
    });
});

describe('nearby pages', () => {
    it('offers two either side, within the pages that exist', () => {
        expect(nearbyPages(5, 20)).toEqual([3, 4, 5, 6, 7]);
        expect(nearbyPages(1, 20)).toEqual([1, 2, 3]);
        expect(nearbyPages(19, 20)).toEqual([17, 18, 19, 20]);
        expect(nearbyPages(1, 1)).toEqual([1]);
    });
});
