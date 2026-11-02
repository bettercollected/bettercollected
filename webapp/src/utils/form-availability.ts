import moment from 'moment/moment';

/** The most responses a limit can name (the server's bound, services/form_availability.py). */
export const MAX_RESPONSE_LIMIT = 1_000_000;

const LOCAL_INPUT_FORMAT = 'YYYY-MM-DDTHH:mm';

/** A stored UTC instant as the value of a `datetime-local` input, in the viewer's time zone ("" for none). */
export function toLocalInputValue(instant?: string | null): string {
    const date = moment.utc(instant || undefined);
    return instant && date.isValid() ? date.local().format(LOCAL_INPUT_FORMAT) : '';
}

/** What a `datetime-local` input holds (the viewer's local time) as the UTC instant to store; null while it is empty or not a date. */
export function fromLocalInputValue(value: string): string | null {
    const date = moment(value, LOCAL_INPUT_FORMAT, true);
    return date.isValid() ? date.utc().toISOString() : null;
}

/** The viewer's own time zone name ("Europe/Amsterdam"), for the line that says what the times are in. */
export function viewerTimeZone(): string {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
        return 'UTC';
    }
}

/**
 * The response limit typed into the settings: a whole number from 1 to
 * MAX_RESPONSE_LIMIT, or empty (no limit). `error` is set for anything else,
 * so a bad value never leaves the page.
 */
export function parseResponseLimit(text: string): { value: number | null; error?: true } {
    const trimmed = text.trim();
    if (!trimmed) return { value: null };
    if (!/^\d+$/.test(trimmed)) return { value: null, error: true };
    const value = Number(trimmed);
    return value >= 1 && value <= MAX_RESPONSE_LIMIT ? { value } : { value: null, error: true };
}

/** Whether an open date is before the close date (either missing: nothing to compare). */
export function opensBeforeCloses(open?: string | null, close?: string | null): boolean {
    if (!open || !close) return true;
    return moment.utc(open).isBefore(moment.utc(close));
}

/** What respondents can do with a form right now, from its settings (the Availability status line). */
export type AvailabilityState =
    | { kind: 'draft' }
    | { kind: 'closed'; since: string }
    | { kind: 'full'; limit: number }
    | { kind: 'not-open'; opens: string; closes?: string }
    | { kind: 'open'; closes?: string };

/**
 * Closed beats everything, then a reached response limit ("full"), then an
 * open date still ahead; a form that is not published is a draft whatever its
 * dates say. A close date that is still ahead is part of "open" and "not open yet".
 */
export function availabilityState(
    form: { isPublished?: boolean; responses?: number; settings?: { formOpenDate?: string | null; formCloseDate?: string | null; responseLimit?: number | null } },
    now: moment.Moment = moment.utc()
): AvailabilityState {
    if (!form.isPublished) return { kind: 'draft' };
    const { formOpenDate, formCloseDate, responseLimit } = form.settings ?? {};
    if (formCloseDate && now.isAfter(moment.utc(formCloseDate))) return { kind: 'closed', since: formCloseDate };
    if (responseLimit && (form.responses ?? 0) >= responseLimit) return { kind: 'full', limit: responseLimit };
    const closes = formCloseDate || undefined;
    if (formOpenDate && now.isBefore(moment.utc(formOpenDate))) return { kind: 'not-open', opens: formOpenDate, closes };
    return { kind: 'open', closes };
}
