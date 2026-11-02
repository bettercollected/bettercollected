import moment from 'moment/moment';
import { describe, expect, it } from 'vitest';

import { utcToLocalDateTimeZoneIn } from './date-utils';
import { MAX_RESPONSE_LIMIT, availabilityState, fromLocalInputValue, opensBeforeCloses, parseResponseLimit, toLocalInputValue } from './form-availability';

describe("an instant read in the viewer's time zone", () => {
    const instant = '2026-11-02T08:00:00+00:00';

    it('is shown with the zone name, in the language', () => {
        expect(utcToLocalDateTimeZoneIn(instant, 'en', 'Europe/Amsterdam')).toBe('2 November 2026, 09:00 CET');
        expect(utcToLocalDateTimeZoneIn(instant, 'nl', 'Europe/Amsterdam')).toBe('2 november 2026, 09:00 CET');
        expect(utcToLocalDateTimeZoneIn(instant, 'en', 'UTC')).toBe('2 November 2026, 08:00 UTC');
        // the same instant, another viewer
        expect(utcToLocalDateTimeZoneIn(instant, 'en', 'America/New_York')).toBe('2 November 2026, 03:00 GMT-5');
    });

    it('follows daylight saving time: the instant is fixed, the wall clock moves', () => {
        expect(utcToLocalDateTimeZoneIn('2026-07-02T08:00:00+00:00', 'en', 'Europe/Amsterdam')).toBe('2 July 2026, 10:00 CEST');
    });

    it('is empty without a usable instant', () => {
        expect(utcToLocalDateTimeZoneIn('', 'en')).toBe('');
        expect(utcToLocalDateTimeZoneIn(undefined, 'en')).toBe('');
        expect(utcToLocalDateTimeZoneIn('banana', 'en')).toBe('');
    });
});

describe('the open date input', () => {
    it('round-trips a stored instant through the local wall clock', () => {
        const stored = '2026-11-02T08:00:00.000Z';
        const typed = toLocalInputValue(stored);
        expect(typed).toMatch(/^2026-11-02T\d{2}:00$/);
        expect(fromLocalInputValue(typed)).toBe(stored);
    });

    it('is empty for no date and null while the field is not a date', () => {
        expect(toLocalInputValue('')).toBe('');
        expect(toLocalInputValue(undefined)).toBe('');
        expect(toLocalInputValue('banana')).toBe('');
        expect(fromLocalInputValue('')).toBeNull();
        expect(fromLocalInputValue('2026-11-02')).toBeNull();
        expect(fromLocalInputValue('2026-13-45T00:00')).toBeNull();
    });
});

describe('the response limit as typed', () => {
    it.each([
        ['', null],
        ['  ', null],
        ['1', 1],
        [' 250 ', 250],
        [String(MAX_RESPONSE_LIMIT), MAX_RESPONSE_LIMIT]
    ])('accepts %j', (text, value) => {
        expect(parseResponseLimit(text)).toEqual({ value });
    });

    it.each(['0', '-3', '2.5', '1e3', 'ten', '12 000', String(MAX_RESPONSE_LIMIT + 1), '+5'])('refuses %j', (text) => {
        expect(parseResponseLimit(text).error).toBe(true);
    });
});

describe('the open date against the close date', () => {
    it('must be before it', () => {
        expect(opensBeforeCloses('2026-11-02T08:00:00Z', '2026-11-09T08:00:00Z')).toBe(true);
        expect(opensBeforeCloses('2026-11-09T08:00:00Z', '2026-11-09T08:00:00Z')).toBe(false);
        expect(opensBeforeCloses('2026-11-10T08:00:00Z', '2026-11-09T08:00:00Z')).toBe(false);
        expect(opensBeforeCloses('2026-11-10T08:00:00Z', '')).toBe(true);
        expect(opensBeforeCloses(undefined, '2026-11-09T08:00:00Z')).toBe(true);
    });
});

describe('the availability state', () => {
    const now = moment.utc('2026-11-02T12:00:00Z');
    const form = (settings: object = {}, extra: object = {}) => ({ isPublished: true, responses: 37, settings, ...extra });

    it('is a draft while the form is not published, whatever its dates say', () => {
        expect(availabilityState(form({ formCloseDate: '2026-01-01T00:00:00Z' }, { isPublished: false }), now)).toEqual({ kind: 'draft' });
    });

    it('is open with nothing scheduled, and says when it closes', () => {
        expect(availabilityState(form(), now)).toEqual({ kind: 'open', closes: undefined });
        expect(availabilityState(form({ formCloseDate: '2026-12-12T17:00:00Z' }), now)).toEqual({ kind: 'open', closes: '2026-12-12T17:00:00Z' });
    });

    it('is not open yet before the open date, still naming the close date', () => {
        expect(availabilityState(form({ formOpenDate: '2026-12-03T08:00:00Z', formCloseDate: '2026-12-12T17:00:00Z' }), now)).toEqual({ kind: 'not-open', opens: '2026-12-03T08:00:00Z', closes: '2026-12-12T17:00:00Z' });
        expect(availabilityState(form({ formOpenDate: '2026-10-01T08:00:00Z' }), now).kind).toBe('open');
    });

    it('is closed once the close date has passed, and that beats everything else', () => {
        expect(availabilityState(form({ formCloseDate: '2026-11-01T17:00:00Z', responseLimit: 10, formOpenDate: '2026-12-03T08:00:00Z' }), now)).toEqual({ kind: 'closed', since: '2026-11-01T17:00:00Z' });
    });

    it('is full once the response limit is reached (and only then)', () => {
        expect(availabilityState(form({ responseLimit: 37 }), now)).toEqual({ kind: 'full', limit: 37 });
        expect(availabilityState(form({ responseLimit: 100 }), now).kind).toBe('open');
        expect(availabilityState(form({ responseLimit: null }, { responses: 5000 }), now).kind).toBe('open');
    });
});
