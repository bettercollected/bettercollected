import { isIsoDate } from '@app/utils/iso-date';

/** The three boxes of a day question, as typed (digits only). */
export interface DayBoxes {
    day: string;
    month: string;
    year: string;
}

const pad = (digits: string, length: number) => digits.padStart(length, '0');

/**
 * What the boxes hold as a stored answer: '' when all three are empty (no
 * answer), else "YYYY-MM-DD" with the day and the month zero-padded to their
 * width and the year as typed: a year of fewer than four digits ("90") is never
 * padded into one ("0090"), so it comes out as text that is not a day
 * ("90-11-05") and is flagged (answer rule FORMAT) where the respondent can fix
 * it. So is a date that does not exist, or a box left empty ("-02-31"): nothing
 * typed is ever dropped.
 */
export function dayBoxesToIso({ day, month, year }: DayBoxes): string {
    if (!day && !month && !year) return '';
    return `${year}-${pad(month, 2)}-${pad(day, 2)}`;
}

/** The boxes for a stored answer (none when it is not shaped like one written by `dayBoxesToIso`). */
export function isoToDayBoxes(value: string): DayBoxes {
    const match = /^(\d{0,4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return { day: '', month: '', year: '' };
    const [, year, month, day] = match;
    // A real day shows its parts as stored; incomplete or impossible typing keeps what was typed (a day or month that is all zeros was left empty).
    if (isIsoDate(value)) return { day, month, year };
    return { day: day === '00' ? '' : day, month: month === '00' ? '' : month, year };
}
