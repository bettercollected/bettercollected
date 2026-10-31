import { describe, expect, it } from 'vitest';

import { dayBoxesToIso, isoToDayBoxes } from './day-boxes';

describe('the boxes of a day question', () => {
    it('make the calendar day, zero-padded', () => {
        expect(dayBoxesToIso({ day: '5', month: '11', year: '1990' })).toBe('1990-11-05');
        expect(dayBoxesToIso({ day: '05', month: '1', year: '2026' })).toBe('2026-01-05');
    });

    it('make no answer when all three are empty', () => {
        expect(dayBoxesToIso({ day: '', month: '', year: '' })).toBe('');
    });

    it('keep what was typed when it is incomplete or does not exist', () => {
        expect(dayBoxesToIso({ day: '31', month: '2', year: '' })).toBe('0000-02-31');
        expect(isoToDayBoxes('0000-02-31')).toEqual({ day: '31', month: '02', year: '' });
        expect(dayBoxesToIso({ day: '31', month: '2', year: '2026' })).toBe('2026-02-31');
        expect(isoToDayBoxes('2026-02-31')).toEqual({ day: '31', month: '02', year: '2026' });
    });

    it('show a stored day in its three boxes', () => {
        expect(isoToDayBoxes('1990-11-05')).toEqual({ day: '05', month: '11', year: '1990' });
        expect(isoToDayBoxes('')).toEqual({ day: '', month: '', year: '' });
        expect(isoToDayBoxes('not a date')).toEqual({ day: '', month: '', year: '' });
    });
});
