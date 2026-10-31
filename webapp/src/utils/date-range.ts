import { format } from 'date-fns';
import { nl as dutch } from 'date-fns/locale/nl';

import { isIsoDate } from '@app/utils/iso-date';

/** The two days of a date range answer. */
export interface DateRangeDays {
    start?: string;
    end?: string;
}

/** The date range a stored answer holds (the slot is `date_range`, `dateRange` in a stored response), whatever it holds. */
export function rawDateRange(answer: any): { start?: unknown; end?: unknown } | undefined {
    const value = answer?.date_range ?? answer?.dateRange;
    return value && typeof value === 'object' && !Array.isArray(value) ? value : undefined;
}

/** The start and end of a date range answer; a missing or not well-formed day is undefined (twin of the server's `date_range_days`). */
export function dateRangeDays(answer: any): { start: string | undefined; end: string | undefined } {
    const value = rawDateRange(answer);
    return { start: isIsoDate(value?.start) ? value.start : undefined, end: isIsoDate(value?.end) ? value.end : undefined };
}

/** The range as one export cell: `YYYY-MM-DD/YYYY-MM-DD` (as written, an ISO 8601 interval), `start/` or `/end` when one end is missing, empty when neither is given. */
export function dateRangeExportText(answer: any): string {
    const value = rawDateRange(answer);
    const start = typeof value?.start === 'string' ? value.start : '';
    const end = typeof value?.end === 'string' ? value.end : '';
    return start || end ? `${start}/${end}` : '';
}

/** A day as the form shows it ("3 November 2026", "3 november 2026"), or the stored text when it is not a day. */
export function longDateText(value: string, language: 'en' | 'nl' = 'en'): string {
    if (!isIsoDate(value)) return value;
    const [year, month, day] = value.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    // years 0 to 99 are read as 19xx by the Date constructor
    date.setFullYear(year);
    return format(date, 'PPP', { locale: language === 'nl' ? dutch : undefined });
}

/** The range as people read it: "3 November 2026 – 7 November 2026" (just that day when only one end is given). Empty when neither is. */
export function dateRangeText(answer: any, language: 'en' | 'nl' = 'en'): string {
    const value = rawDateRange(answer);
    const start = typeof value?.start === 'string' ? value.start : '';
    const end = typeof value?.end === 'string' ? value.end : '';
    const shown = [start, end].filter(Boolean).map((day) => longDateText(day, language));
    return shown.join(' \u2013 ');
}
