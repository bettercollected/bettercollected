/** How many characters of a receipt number staff screens show. */
export const RECEIPT_NUMBER_SHOWN = 8;

/**
 * The start of a receipt (submission) number, for staff screens: "#0a1b2c3d…".
 *
 * The full number is a bearer token (anyone holding it can read the response
 * without logging in), so staff screens never put the whole value in the DOM:
 * not as text, and not in a title, aria-* or data-* attribute. The start is
 * enough to match a request against the number a responder quotes.
 *
 * A fixed length rather than "up to the first dash", so a number without
 * dashes is shortened too.
 */
export function shortReceiptNumber(number?: string | null): string {
    if (!number) return '';
    return `#${number.slice(0, RECEIPT_NUMBER_SHOWN)}…`;
}
