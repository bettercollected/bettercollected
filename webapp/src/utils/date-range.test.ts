import { describe, expect, it } from 'vitest';

import { dateRangeDays, dateRangeExportText, dateRangeText, longDateText, rawDateRange } from './date-range';

const range = (start?: string, end?: string) => ({ type: 'date_range', date_range: { start, end } });

describe('date range answers', () => {
    it('reads the slot as the transport spells it, and as a stored response may', () => {
        expect(rawDateRange(range('2026-11-03', '2026-11-07'))).toEqual({ start: '2026-11-03', end: '2026-11-07' });
        expect(rawDateRange({ dateRange: { start: '2026-11-03', end: '2026-11-07' } })).toEqual({ start: '2026-11-03', end: '2026-11-07' });
        expect(rawDateRange({ date_range: [] })).toBeUndefined();
        expect(rawDateRange(undefined)).toBeUndefined();
    });

    it('gives only well-formed days, as the server does', () => {
        expect(dateRangeDays(range('2026-11-03', '2026-11-07'))).toEqual({ start: '2026-11-03', end: '2026-11-07' });
        expect(dateRangeDays(range('2026-02-30', '2026-11-07'))).toEqual({ start: undefined, end: '2026-11-07' });
        expect(dateRangeDays(range('03-11-2026', ''))).toEqual({ start: undefined, end: undefined });
    });

    it('is one export cell: both days, one end, or empty', () => {
        expect(dateRangeExportText(range('2026-11-03', '2026-11-07'))).toBe('2026-11-03/2026-11-07');
        expect(dateRangeExportText(range('2026-11-03'))).toBe('2026-11-03/');
        expect(dateRangeExportText(range(undefined, '2026-11-07'))).toBe('/2026-11-07');
        expect(dateRangeExportText(range('', ''))).toBe('');
        expect(dateRangeExportText({})).toBe('');
    });

    it('reads as two long dates in the language of the form', () => {
        expect(longDateText('2026-11-03')).toBe('3 November 2026');
        expect(dateRangeText(range('2026-11-03', '2026-11-07'))).toBe('3 November 2026 – 7 November 2026');
        expect(dateRangeText(range('2026-11-03', '2026-11-07'), 'nl')).toBe('3 november 2026 – 7 november 2026');
        expect(dateRangeText(range('2026-11-03'), 'nl')).toBe('3 november 2026');
        expect(dateRangeText(range('', ''))).toBe('');
        expect(longDateText('soon')).toBe('soon');
    });
});
