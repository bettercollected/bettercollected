import { describe, expect, it } from 'vitest';

import { utcToLocalDateTimeZoneIn } from './date-utils';
import { MAX_RESPONSE_LIMIT, fromLocalInputValue, opensBeforeCloses, parseResponseLimit, toLocalInputValue } from './form-availability';

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
