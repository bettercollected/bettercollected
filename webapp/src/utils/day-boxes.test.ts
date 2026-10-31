import { describe, expect, it } from 'vitest';

import { dayBoxesToIso, isoToDayBoxes } from './day-boxes';
import { isDay } from './iso-date';

describe('the boxes of a day question', () => {
    it('make the calendar day, zero-padded', () => {
        expect(dayBoxesToIso({ day: '5', month: '11', year: '1990' })).toBe('1990-11-05');
        expect(dayBoxesToIso({ day: '05', month: '1', year: '2026' })).toBe('2026-01-05');
    });

    it('make no answer when all three are empty', () => {
        expect(dayBoxesToIso({ day: '', month: '', year: '' })).toBe('');
    });

    it('keep what was typed when it is incomplete or does not exist', () => {
        expect(dayBoxesToIso({ day: '31', month: '2', year: '' })).toBe('-02-31');
        expect(isoToDayBoxes('-02-31')).toEqual({ day: '31', month: '02', year: '' });
        expect(dayBoxesToIso({ day: '31', month: '2', year: '2026' })).toBe('2026-02-31');
        expect(isoToDayBoxes('2026-02-31')).toEqual({ day: '31', month: '02', year: '2026' });
    });

    it('never pad a short year into a year that was not typed', () => {
        expect(dayBoxesToIso({ day: '5', month: '11', year: '90' })).toBe('90-11-05');
        expect(dayBoxesToIso({ day: '5', month: '11', year: '199' })).toBe('199-11-05');
        expect(dayBoxesToIso({ day: '5', month: '11', year: '0' })).toBe('0-11-05');
        expect(isDay(dayBoxesToIso({ day: '5', month: '11', year: '90' }))).toBe(false);
        expect(isDay(dayBoxesToIso({ day: '5', month: '11', year: '1990' }))).toBe(true);
        // what was typed comes back into the boxes
        expect(isoToDayBoxes('90-11-05')).toEqual({ day: '05', month: '11', year: '90' });
        expect(isoToDayBoxes('199-11-05')).toEqual({ day: '05', month: '11', year: '199' });
    });

    it('count a year from 1000 on, in the same way as the server', () => {
        expect(isDay('1000-01-01')).toBe(true);
        expect(isDay('0999-12-31')).toBe(false);
        expect(isDay('0090-11-05')).toBe(false);
        expect(isDay('2026-02-30')).toBe(false);
    });

    it('show a stored day in its three boxes', () => {
        expect(isoToDayBoxes('1990-11-05')).toEqual({ day: '05', month: '11', year: '1990' });
        expect(isoToDayBoxes('')).toEqual({ day: '', month: '', year: '' });
        expect(isoToDayBoxes('not a date')).toEqual({ day: '', month: '', year: '' });
    });
});
