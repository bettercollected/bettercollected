import moment from 'moment/moment';

export const utcToLocalDate = (dateStr: any) => moment.utc(dateStr).local().format('Do MMMM, YYYY');

export const utcToLocalTime = (dateStr: any) => moment.utc(dateStr).local().format('hh:mm A');

export const utcToLocalDateTIme = (dateStr: any) => moment.utc(dateStr).local().format('Do MMMM, YYYY hh:mm A');

/**
 * A UTC date as a full local date and time with the time zone, for places that
 * must be unambiguous: "30 October 2026, 11:10:05 CET". `timeZone` defaults to
 * the viewer's own zone.
 */
export function utcToLocalDateTimeWithZone(dateStr: any, timeZone?: string): string {
    const date = moment.utc(dateStr);
    if (!dateStr || !date.isValid()) return '';
    return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZoneName: 'short', timeZone }).format(date.toDate());
}

const intlLocale = (language: string) => (language === 'nl' ? 'nl-NL' : 'en-GB');

/** A UTC date as a local date in a language: "24 October 2026" / "24 oktober 2026". */
export function utcToLocalDateIn(dateStr: any, language: string): string {
    const date = moment.utc(dateStr);
    return dateStr && date.isValid() ? new Intl.DateTimeFormat(intlLocale(language), { dateStyle: 'long' }).format(date.toDate()) : '';
}

/**
 * A calendar day written YYYY-MM-DD (an answer to a date, day or date range
 * question) in the app's date style and a language: "5 November 1990" /
 * "5 november 1990". A day has no time zone, so it is never moved by the
 * reader's. Text that is not a real day comes back as it is.
 */
export function calendarDayIn(value: string, language: string): string {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return value;
    const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
    // setUTCFullYear, not the constructor: years 0 to 99 are not read as 1900 to 1999
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, day);
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return value;
    return new Intl.DateTimeFormat(intlLocale(language), { dateStyle: 'long', timeZone: 'UTC' }).format(date);
}

/** A UTC date as a local date and time in a language: "24 October 2026 at 14:05" / "24 oktober 2026 om 14:05". */
export function utcToLocalDateTimeIn(dateStr: any, language: string): string {
    const date = moment.utc(dateStr);
    return dateStr && date.isValid() ? new Intl.DateTimeFormat(intlLocale(language), { dateStyle: 'long', timeStyle: 'short' }).format(date.toDate()) : '';
}

/**
 * A UTC instant as a local date and time in a language, with the time zone's
 * short name: "2 November 2026, 09:00 CET" / "2 november 2026, 09:00 CET".
 * The zone defaults to the viewer's own, so a respondent reads it in theirs.
 */
export function utcToLocalDateTimeZoneIn(dateStr: any, language: string, timeZone?: string): string {
    const date = moment.utc(dateStr);
    if (!dateStr || !date.isValid()) return '';
    const locale = intlLocale(language);
    const day = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', year: 'numeric', timeZone }).format(date.toDate());
    const time = new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'short', timeZone }).format(date.toDate());
    return `${day}, ${time}`;
}

const RELATIVE_UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['year', 365 * 24 * 3600],
    ['month', 30 * 24 * 3600],
    ['day', 24 * 3600],
    ['hour', 3600],
    ['minute', 60]
];

/**
 * How long ago a UTC date was, in a language: "4 hours ago" / "4 uur geleden",
 * and "now" / "nu" under a minute (or for a date a little ahead of the clock).
 * Empty for a missing or invalid date.
 */
export function utcToRelativeIn(dateStr: any, language: string, now: number = Date.now()): string {
    const date = moment.utc(dateStr);
    if (!dateStr || !date.isValid()) return '';
    const seconds = Math.max(0, Math.floor((now - date.valueOf()) / 1000));
    const format = new Intl.RelativeTimeFormat(intlLocale(language), { numeric: 'auto' });
    const [unit, size] = RELATIVE_UNITS.find(([, size]) => seconds >= size) ?? ['second', 1];
    return unit === 'second' ? format.format(0, 'second') : format.format(-Math.floor(seconds / size), unit);
}

/**
 * Formats a date and time in the "yyyy-mm-dd:hh:mm:ss" format, optionally adding days and hours.
 *
 * **/
export function getApiFormattedDateTime(dtStr = '', hoursToAdd = 0) {
    const currentDateTime = new Date();
    currentDateTime.setHours(currentDateTime.getHours() + hoursToAdd);

    if (dtStr.length === 0) {
        return `${currentDateTime.toISOString().slice(0, 19).replace('T', ':')}`;
    } else {
        const timeString = currentDateTime.toLocaleTimeString('en-US', { hour12: false });
        return `${dtStr}:${timeString}`;
    }
}

type dateType = 'day' | 'month' | 'year' | '';

export function validateDate(date: string, type: dateType) {
    switch (type) {
        case 'day':
            return /^$|^(?:[0-9]|[012][0-9]|3[012])$/.test(date) ? '' : 'Day format is not correct. It should be between 1-32.';
        case 'month':
            return /^$|^(0?[0-9]|1[0-2])$/.test(date) ? '' : 'Month format is not correct. It should be between 1-12.';
        case 'year':
            return /^$|^\d{0,4}$/.test(date) ? '' : 'Year format is not correct. It should be 4 digit number.';
        default:
            return /^$|^\d{4}$/.test(date) ? '' : 'Year format is not correct. It should be 4 digit number.';
    }
}

export function getUnformattedDate(date: string): Array<string> {
    return date.split('-');
}

export function getFormattedDate(value: string, date: string, type: dateType): string {
    const dateValue = date.split('-');
    switch (type) {
        case 'year':
            return `${value}-${dateValue[1]}-${dateValue[2]}`;
        case 'month':
            return `${dateValue[0]}-${value}-${dateValue[2]}`;
        case 'day':
            return `${dateValue[0]}-${dateValue[1]}-${value}`;
        default:
            return ``;
    }
}
