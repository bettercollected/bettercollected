import moment from 'moment/moment';

export const utcToLocalDate = (dateStr: any) => moment.utc(dateStr).local();

export const parseDate = (dateStr: any) => Date.parse(dateStr);

export const parseDateStrToDate = (dateStr: any) => new Date(parseDate(dateStr));

export const toHourMinStr = (date: Date) =>
    date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: 'numeric',
        hour12: true
    });

export const toMonthDateYearStr = (date: Date) =>
    date.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });

export const toLocaleString = (date: Date) =>
    date.toLocaleString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
        hour12: true
    });

export const toLocaleStringFromDateString = (date: string) =>
    new Date(date).toLocaleString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
        hour12: true
    });

/**
 * Formats a date and time in the "yyyy-mm-dd:hh:mm:ss" format, optionally adding days and hours.
 *
 * **/
export function getApiFormattedDateTime(dtStr = '', hoursToAdd = 0) {
    const currentDateTime = new Date();
    currentDateTime.setHours(currentDateTime.getHours() + hoursToAdd);

    if (dtStr.length === 0) {
        const formattedDateTime = `${currentDateTime.toISOString().slice(0, 19).replace('T', ':')}`;
        return formattedDateTime;
    } else {
        const timeString = currentDateTime.toLocaleTimeString('en-US', { hour12: false });
        return `${dtStr}:${timeString}`;
    }
}
