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
        month: 'short',
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
