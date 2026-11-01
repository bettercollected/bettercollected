/**
 * What an address answer may hold. An answer is `{ type: 'address', address: {...} }` with the
 * parts `street`, `house_number`, `house_number_addition`, `postcode`, `city` and `country` (an
 * ISO 3166-1 alpha-2 code, see countries.ts). Every part is text, stored the way it is shown:
 * trimmed, in Unicode form C, without control or format characters (zero-width and bidirectional
 * marks), and within the caps below. A Dutch address (`NL`) is held to the Dutch forms: a
 * postcode written `1234 AB` (one space, upper case; the letters not `SA`, `SD` or `SS`) and a
 * house number of one to five digits. Nothing here knows whether an address exists: a street and
 * a city a lookup filled in are as unverified as typed ones. The server's twin is common
 * `address.py`; the shared answer-validation corpus runs against both.
 */
import { isCountryCode } from '@app/utils/countries';

export interface AddressParts {
    street?: string;
    house_number?: string;
    house_number_addition?: string;
    postcode?: string;
    city?: string;
    country?: string;
}

export const PARTS = ['street', 'house_number', 'house_number_addition', 'postcode', 'city', 'country'] as const;
export type AddressPart = (typeof PARTS)[number];

/** Caps of one part, in characters; the country is a two-letter code. */
export const STREET_MAX = 100;
export const CITY_MAX = 100;
export const HOUSE_NUMBER_MAX = 10;
export const ADDITION_MAX = 10;
export const POSTCODE_MAX = 12;
export const PART_MAX: Readonly<Record<string, number>> = {
    street: STREET_MAX,
    house_number: HOUSE_NUMBER_MAX,
    house_number_addition: ADDITION_MAX,
    postcode: POSTCODE_MAX,
    city: CITY_MAX,
    country: 2
};

export const NL = 'NL';

/** Rule codes, as the server says them (lower case). */
export type AddressRule = 'required' | 'format' | 'country' | 'too_long';

// Control (Cc), format (Cf: zero-width and bidirectional marks, the byte order mark, the soft hyphen) and
// line/paragraph separators (Zl, Zp) never belong in an address (the server's twin: common `address.py`).
const FORBIDDEN = /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/u;
// What Python's str.strip() removes (the server's notion of "trimmed"), not what JavaScript's trim() does (it also strips U+FEFF).
const PY_SPACE = '\\t\\n\\v\\f\\r \\x1c-\\x1f\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const EDGE_SPACE = new RegExp(`^[${PY_SPACE}]|[${PY_SPACE}]$`);
const EDGES = new RegExp(`^[${PY_SPACE}]+|[${PY_SPACE}]+$`, 'g');

/** Python's `str.strip()`. */
export const pyStrip = (value: string): string => value.replace(EDGES, '');

const NL_POSTCODE = /^[1-9][0-9]{3} [A-Z]{2}$/;
const NL_POSTCODE_LOOSE = /^([1-9][0-9]{3}) ?([A-Za-z]{2})$/;
const NL_BAD_LETTERS = new Set(['SA', 'SD', 'SS']);
const NL_HOUSE_NUMBER = /^[1-9][0-9]{0,4}$/;
const NL_ADDITION = /^[0-9A-Za-z][0-9A-Za-z /-]{0,9}$/;
const OTHER_POSTCODE = /^[0-9A-Za-z][0-9A-Za-z -]{0,10}[0-9A-Za-z]$/;

/** The number of characters (code points, as the server counts them) of a part. */
export const partLength = (value: string): number => Array.from(value).length;

/** Is `value` well-formed text for an address part: trimmed, in Unicode form C, `minimum` to `limit` characters, nothing forbidden? */
export function isCleanText(value: unknown, limit: number, minimum = 1): value is string {
    if (typeof value !== 'string') return false;
    const length = partLength(value);
    return length >= minimum && length <= limit && !EDGE_SPACE.test(value) && value === value.normalize('NFC') && !FORBIDDEN.test(value);
}

/** Is `value` a Dutch postcode in its stored form (`1234 AB`)? */
export const isNlPostcode = (value: unknown): value is string => typeof value === 'string' && NL_POSTCODE.test(value) && !NL_BAD_LETTERS.has(value.slice(5));

/** A Dutch postcode as typed (`1234ab`, `1234 AB`, surrounding space ignored) in its stored form, or undefined when it is not one. */
export function canonicalNlPostcode(value: unknown): string | undefined {
    if (typeof value !== 'string') return undefined;
    const found = NL_POSTCODE_LOOSE.exec(pyStrip(value));
    if (!found) return undefined;
    const canonical = `${found[1]} ${found[2].toUpperCase()}`;
    return isNlPostcode(canonical) ? canonical : undefined;
}

/** Is `value` a Dutch house number: one to five digits, not starting with 0? */
export const isNlHouseNumber = (value: unknown): value is string => typeof value === 'string' && NL_HOUSE_NUMBER.test(value);

/** Is `value` a Dutch house number addition (a letter, a number or a short word)? */
export const isNlAddition = (value: unknown): value is string => typeof value === 'string' && NL_ADDITION.test(value) && !value.endsWith(' ');

/** Is `value` a postcode of another country: letters, digits, spaces and hyphens, two to POSTCODE_MAX characters? */
export const isOtherPostcode = (value: unknown): value is string => typeof value === 'string' && value.length >= 2 && value.length <= POSTCODE_MAX && OTHER_POSTCODE.test(value) && !value.includes('  ');

/** The two values a lookup takes, from what was typed (the postcode as `1234AB`, no space), or undefined when either is not valid. */
export function lookupKey(postcode: unknown, houseNumber: unknown): { postcode: string; houseNumber: string } | undefined {
    const canonical = canonicalNlPostcode(postcode);
    const number = typeof houseNumber === 'string' ? pyStrip(houseNumber) : undefined;
    if (!canonical || number === undefined || !isNlHouseNumber(number)) return undefined;
    return { postcode: canonical.replace(' ', ''), houseNumber: number };
}

/** The parts of an answer (or of its `address` slot) that are text, by name; undefined when it has no address. */
export function answerAddress(answer: any): AddressParts | undefined {
    const value = answer && typeof answer === 'object' && 'address' in answer ? answer.address : answer;
    if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
    const parts: AddressParts = {};
    for (const part of PARTS) if (typeof value[part] === 'string') parts[part] = value[part];
    return parts;
}

/** Is `value` an address answer's shape: an object whose keys are some of the six parts and whose values are text or null? */
export function addressShape(value: unknown): boolean {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    return Object.entries(value as Record<string, unknown>).every(([key, part]) => (PARTS as ReadonlyArray<string>).includes(key) && (part === null || part === undefined || typeof part === 'string'));
}

/** Is any part but the country given? (A country alone is no answer.) */
export const hasAnyPart = (value: unknown): boolean => !!value && typeof value === 'object' && PARTS.some((part) => part !== 'country' && typeof (value as any)[part] === 'string' && (value as any)[part] !== '');

/**
 * What no stored address may break whatever its question says: a part that is not clean text (untrimmed, not in
 * Unicode form C, a control or format character) is `format`, one over its cap `too_long`. Undefined for
 * something that is not the shape (the type check says so).
 */
export function hardProblem(value: unknown): AddressRule | undefined {
    if (!addressShape(value)) return undefined;
    let problem: AddressRule | undefined;
    for (const [part, limit] of Object.entries(PART_MAX)) {
        const text = (value as any)[part];
        if (!text) continue;
        if (partLength(text) > limit) return 'too_long';
        if (!isCleanText(text, limit)) problem = 'format';
    }
    return problem;
}

/**
 * The rules an answered address breaks, without repeats, in order of first appearance: `required` (street, house
 * number, postcode, city or, when the question allows several countries, the country is missing), `format` (a part
 * is not what its country writes, the country not a code), `country` (not one the question allows), `too_long`.
 * A single allowed country is assumed when none is given. Nothing for something that is not an address or has no
 * part at all (Required's to say). Twin of common `address.problems`.
 */
export function addressProblems(value: unknown, allowedCountries?: ReadonlyArray<string>): AddressRule[] {
    if (!addressShape(value)) return [];
    const raw = value as Record<string, string | null | undefined>;
    if (!PARTS.some((part) => raw[part])) return [];
    const allowed = allowedCountries && allowedCountries.length ? allowedCountries : [NL];
    const found: AddressRule[] = [];
    const add = (rule: AddressRule) => {
        if (!found.includes(rule)) found.push(rule);
    };
    const text: Record<string, string> = {};
    for (const part of PARTS) text[part] = raw[part] ?? '';
    const country = text.country || (allowed.length === 1 ? allowed[0] : '');
    for (const part of ['street', 'house_number', 'postcode', 'city']) if (!text[part]) add('required');
    if (!country) add('required');
    if (text.country) {
        if (!isCountryCode(text.country)) add('format');
        else if (!allowed.includes(text.country)) add('country');
    }
    for (const [part, limit] of Object.entries(PART_MAX)) if (partLength(text[part]) > limit) add('too_long');
    const within = (part: string) => text[part] && partLength(text[part]) <= PART_MAX[part];
    if (country === NL) {
        if (within('postcode') && !isNlPostcode(text.postcode)) add('format');
        if (within('house_number') && !isNlHouseNumber(text.house_number)) add('format');
        if (within('house_number_addition') && !isNlAddition(text.house_number_addition)) add('format');
    } else if (country) {
        if (within('postcode') && !isOtherPostcode(text.postcode)) add('format');
    }
    for (const part of ['street', 'house_number', 'house_number_addition', 'city']) if (within(part) && !isCleanText(text[part], PART_MAX[part])) add('format');
    return found;
}

/** The address as one line for a table, an export or a message: `street number addition, postcode city` and the country code unless it is NL; '' when it is not an address. Twin of common `address.one_line`. */
export function addressLine(value: unknown): string {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
    const text = (part: string): string => {
        const found = (value as any)[part];
        return typeof found === 'string' ? pyStrip(found) : '';
    };
    const street = [text('street'), text('house_number'), text('house_number_addition')].filter(Boolean).join(' ');
    const town = [text('postcode'), text('city')].filter(Boolean).join(' ');
    const country = text('country');
    const parts = [street, town].filter(Boolean);
    if (country && country !== NL && parts.length) parts.push(country);
    return parts.join(', ');
}

/** The address as the lines a response page shows: street, number and addition; postcode and city; the country's name unless it is NL. Empty when it is not an address. */
export function addressLines(value: unknown, countryNameOf: (code: string) => string): string[] {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
    const text = (part: string): string => {
        const found = (value as any)[part];
        return typeof found === 'string' ? pyStrip(found) : '';
    };
    const country = text('country');
    const lines = [[text('street'), text('house_number'), text('house_number_addition')], [text('postcode'), text('city')]].map((line) => line.filter(Boolean).join(' ')).filter(Boolean);
    if (country && country !== NL && lines.length) lines.push(countryNameOf(country));
    return lines;
}

/**
 * Which part breaks which rule, for the field to say next to its box (the question's own message is `addressProblems`'
 * first one). Same rules as `addressProblems`, by part; the parts that are fine are left out. Nothing for something that
 * is not an address or has no part at all.
 */
export function partProblems(value: unknown, allowedCountries?: ReadonlyArray<string>): Partial<Record<AddressPart, AddressRule>> {
    if (!addressShape(value)) return {};
    const raw = value as Record<string, string | null | undefined>;
    if (!PARTS.some((part) => raw[part])) return {};
    const allowed = allowedCountries && allowedCountries.length ? allowedCountries : [NL];
    const out: Partial<Record<AddressPart, AddressRule>> = {};
    const text: Record<string, string> = {};
    for (const part of PARTS) text[part] = raw[part] ?? '';
    const country = text.country || (allowed.length === 1 ? allowed[0] : '');
    for (const part of ['street', 'house_number', 'postcode', 'city'] as const) if (!text[part]) out[part] = 'required';
    if (!country) out.country = 'required';
    if (text.country) {
        if (!isCountryCode(text.country)) out.country = 'format';
        else if (!allowed.includes(text.country)) out.country = 'country';
    }
    const within = (part: string) => text[part] && partLength(text[part]) <= PART_MAX[part];
    for (const part of ['street', 'house_number', 'house_number_addition', 'postcode', 'city'] as const) if (text[part] && partLength(text[part]) > PART_MAX[part]) out[part] = 'too_long';
    const bad = (part: AddressPart) => {
        if (!out[part]) out[part] = 'format';
    };
    if (country === NL) {
        if (within('postcode') && !isNlPostcode(text.postcode)) bad('postcode');
        if (within('house_number') && !isNlHouseNumber(text.house_number)) bad('house_number');
        if (within('house_number_addition') && !isNlAddition(text.house_number_addition)) bad('house_number_addition');
    } else if (country) {
        if (within('postcode') && !isOtherPostcode(text.postcode)) bad('postcode');
    }
    for (const part of ['street', 'house_number', 'house_number_addition', 'city'] as const) if (within(part) && !isCleanText(text[part], PART_MAX[part])) bad(part);
    return out;
}

/** Does this form ask an address question that looks up street and city (a Dutch address allowed, the question's lookup not off)? The respondent's form says it only while the server offers the lookup (the server turns each question's lookup off otherwise), so this is also what the privacy panel needs. */
export function formLooksUpAddresses(form: { fields?: Array<any> } | null | undefined): boolean {
    const visit = (fields: Array<any> | undefined): boolean =>
        (fields ?? []).some((field) => {
            if (field?.type === 'address' && !field.internal) {
                const countries = field.properties?.countries;
                return field.properties?.addressLookup !== false && (!Array.isArray(countries) || !countries.length || countries.includes(NL));
            }
            return visit(field?.properties?.fields);
        });
    return visit(form?.fields);
}
