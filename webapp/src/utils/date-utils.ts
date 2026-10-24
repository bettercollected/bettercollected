import moment from 'moment/moment';

export const utcToLocalDate = (dateStr: any) => moment.utc(dateStr).local().format('Do MMMM, YYYY');

export const utcToLocalTime = (dateStr: any) => moment.utc(dateStr).local().format('hh:mm A');

export const utcToLocalDateTIme = (dateStr: any) => moment.utc(dateStr).local().format('Do MMMM, YYYY hh:mm A');

const intlLocale = (language: string) => (language === 'nl' ? 'nl-NL' : 'en-GB');

/** A UTC date as a local date in a language: "24 October 2026" / "24 oktober 2026". */
export function utcToLocalDateIn(dateStr: any, language: string): string {
    const date = moment.utc(dateStr);
    return dateStr && date.isValid() ? new Intl.DateTimeFormat(intlLocale(language), { dateStyle: 'long' }).format(date.toDate()) : '';
}

/** A UTC date as a local date and time in a language: "24 October 2026 at 14:05" / "24 oktober 2026 om 14:05". */
export function utcToLocalDateTimeIn(dateStr: any, language: string): string {
    const date = moment.utc(dateStr);
    return dateStr && date.isValid() ? new Intl.DateTimeFormat(intlLocale(language), { dateStyle: 'long', timeStyle: 'short' }).format(date.toDate()) : '';
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
