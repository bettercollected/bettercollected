import { describe, expect, it } from 'vitest';

import { utcToRelativeIn } from '@app/utils/date-utils';

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
