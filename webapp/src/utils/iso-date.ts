const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** The earliest year of a day typed in three boxes, or of an end of a date range (backend `MIN_DAY_YEAR`). */
export const MIN_DAY_YEAR = 1000;

/** Is `value` a real calendar date in a year from MIN_DAY_YEAR on? A year with fewer than four digits ("90") is a typing slip (backend `is_day`). */
export function isDay(value: unknown): value is string {
    return isIsoDate(value) && Number(value.slice(0, 4)) >= MIN_DAY_YEAR;
}

/** Is `value` a real calendar date written exactly as YYYY-MM-DD? */
export function isIsoDate(value: unknown): value is string {
    if (typeof value !== 'string') return false;
    const match = ISO_DATE.exec(value);
    if (!match) return false;
    const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
    // Years 1 to 9999, as the server reads them (there is no year 0)
    if (year < 1) return false;
    // setUTCFullYear, not Date.UTC: years 0 to 99 are not read as 1900 to 1999
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, day);
    return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}
