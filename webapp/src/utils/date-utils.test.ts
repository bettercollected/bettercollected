import { describe, expect, it } from 'vitest';

import { calendarDayIn, utcToLocalDateTimeWithZone, utcToRelativeIn } from '@app/utils/date-utils';

const NOW = Date.parse('2026-10-29T12:00:00Z');
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

describe('utcToRelativeIn', () => {
    it('says how long ago in Dutch', () => {
        expect(utcToRelativeIn(ago(4 * 3600), 'nl', NOW)).toBe('4 uur geleden');
        expect(utcToRelativeIn(ago(5 * 60), 'nl', NOW)).toBe('5 minuten geleden');
        expect(utcToRelativeIn(ago(3 * 86400), 'nl', NOW)).toBe('3 dagen geleden');
        expect(utcToRelativeIn(ago(2 * 30 * 86400), 'nl', NOW)).toBe('2 maanden geleden');
        expect(utcToRelativeIn(ago(2 * 365 * 86400), 'nl', NOW)).toBe('2 jaar geleden');
    });

    it('says how long ago in English', () => {
        expect(utcToRelativeIn(ago(4 * 3600), 'en', NOW)).toBe('4 hours ago');
        expect(utcToRelativeIn(ago(5 * 60), 'en', NOW)).toBe('5 minutes ago');
        expect(utcToRelativeIn(ago(3 * 86400), 'en', NOW)).toBe('3 days ago');
    });

    it('never mixes the languages', () => {
        const dutch = utcToRelativeIn(ago(4 * 3600), 'nl', NOW);
        expect(dutch).not.toMatch(/ago|hours?/);
        expect(utcToRelativeIn(ago(4 * 3600), 'en', NOW)).not.toMatch(/geleden|uur/);
    });

    it('says "now" under a minute, and for a date a little ahead of the clock', () => {
        expect(utcToRelativeIn(ago(10), 'nl', NOW)).toBe('nu');
        expect(utcToRelativeIn(ago(10), 'en', NOW)).toBe('now');
        expect(utcToRelativeIn(ago(-30), 'nl', NOW)).toBe('nu');
    });

    it('is empty for a missing or invalid date', () => {
        expect(utcToRelativeIn(undefined, 'nl', NOW)).toBe('');
        expect(utcToRelativeIn('not a date', 'en', NOW)).toBe('');
    });
});

describe('utcToLocalDateTimeWithZone', () => {
    it('shows the full date and time with the zone, in the zone asked for', () => {
        expect(utcToLocalDateTimeWithZone('2026-10-30T09:10:05Z', 'UTC')).toMatch(/^30 October 2026(,| at) 09:10:05 UTC$/);
        expect(utcToLocalDateTimeWithZone('2026-10-30T09:10:05Z', 'Europe/Amsterdam')).toMatch(/^30 October 2026(,| at) 10:10:05 (CET|GMT\+1)$/);
    });

    it('writes it in Dutch when asked', () => {
        expect(utcToLocalDateTimeWithZone('2026-10-30T09:10:05Z', 'UTC', 'nl')).toMatch(/^30 oktober 2026( om|,)? 09:10:05 UTC$/);
    });

    it('is empty for a missing or invalid date', () => {
        expect(utcToLocalDateTimeWithZone(undefined)).toBe('');
        expect(utcToLocalDateTimeWithZone('not a date')).toBe('');
    });
});

describe('calendarDayIn', () => {
    it('writes a day in the app\'s date style, in the language', () => {
        expect(calendarDayIn('1990-11-05', 'en')).toBe('5 November 1990');
        expect(calendarDayIn('1990-11-05', 'nl')).toBe('5 november 1990');
        expect(calendarDayIn('2026-02-28', 'en')).toBe('28 February 2026');
    });

    it('never moves the day with the reader\'s time zone', () => {
        const zone = process.env.TZ;
        for (const tz of ['Pacific/Auckland', 'America/Los_Angeles', 'UTC']) {
            process.env.TZ = tz;
            expect(calendarDayIn('2026-12-31', 'en')).toBe('31 December 2026');
            expect(calendarDayIn('2026-01-01', 'en')).toBe('1 January 2026');
        }
        process.env.TZ = zone;
    });

    it('returns what is not a real day as it is', () => {
        expect(calendarDayIn('2026-02-30', 'en')).toBe('2026-02-30');
        expect(calendarDayIn('90-11-05', 'en')).toBe('90-11-05');
        expect(calendarDayIn('', 'en')).toBe('');
        expect(calendarDayIn('soon', 'nl')).toBe('soon');
    });
});
