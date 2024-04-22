type dateType = 'day' | 'month' | 'year' | '';

export function validateDate(date: string, type: dateType) {
    switch (type) {
        case 'day':
            return /^$|^(?:[0-9]|[012][0-9]|3[012])$/.test(date)
                ? ''
                : 'Day format is not correct. It should be between 1-32.';
        case 'month':
            return /^$|^(0?[0-9]|1[0-2])$/.test(date)
                ? ''
                : 'Month format is not correct. It should be between 1-12.';
        case 'year':
            return /^$|^\d{0,4}$/.test(date)
                ? ''
                : 'Year format is not correct. It should be 4 digit number.';
        default:
            return /^$|^\d{4}$/.test(date)
                ? ''
                : 'Year format is not correct. It should be 4 digit number.';
    }
}

export function getUnformattedDate(date: string): Array<string> {
    return date.split('-');
}

export function getFormattedDate(date: {
    day: string;
    month: string;
    year: string;
}): string {
    return `${date.day}-${date.month}-${date.year}`;
}
