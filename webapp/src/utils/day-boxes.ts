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
 * answer), else "YYYY-MM-DD" with each box zero-padded to its width. A date
 * that does not exist, or a box left empty, comes out as text that is not a
 * calendar date ("0000-02-31"), so it is flagged (answer rule FORMAT) where the
 * respondent can fix it, never dropped.
 */
export function dayBoxesToIso({ day, month, year }: DayBoxes): string {
    if (!day && !month && !year) return '';
    return `${pad(year, 4)}-${pad(month, 2)}-${pad(day, 2)}`;
}

/** The boxes for a stored answer (none when it is not shaped YYYY-MM-DD). */
export function isoToDayBoxes(value: string): DayBoxes {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return { day: '', month: '', year: '' };
    const [, year, month, day] = match;
    // A real date shows its parts as stored; incomplete or impossible typing keeps what was typed (a box that is all zeros was left empty).
    if (isIsoDate(value)) return { day, month, year };
    return { day: day === '00' ? '' : day, month: month === '00' ? '' : month, year: year === '0000' ? '' : year };
}
