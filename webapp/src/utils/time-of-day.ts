/**
 * A time question's answer: a wall-clock time written "HH:MM", 24 hours,
 * zero-padded, no seconds and no time zone (a time like a calendar day is
 * not an instant). Ordered comparisons (limits, logic, rules) compare the
 * text, which sorts as the time does. The server's twin: common
 * `currencies.is_time`.
 */

const TIME = /^([01][0-9]|2[0-3]):([0-5][0-9])$/;

/** Is `value` a time written exactly HH:MM (00:00 to 23:59)? */
export function isTime(value: unknown): value is string {
    return typeof value === 'string' && TIME.test(value);
}

/** Minutes since midnight of a valid HH:MM. */
export function minutesOf(value: string): number {
    return Number(value.slice(0, 2)) * 60 + Number(value.slice(3));
}
