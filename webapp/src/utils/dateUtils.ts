import moment from 'moment/moment';

export const utcToLocalDate = (dateStr: any) => moment.utc(dateStr).local().format('Do MMMM, YYYY');

export const utcToLocalTime = (dateStr: any) => moment.utc(dateStr).local().format('hh:mm A');

export const utcToLocalDateTIme = (dateStr: any) => moment.utc(dateStr).local().format('Do MMMM, YYYY hh:mm A');

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