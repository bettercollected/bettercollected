/**
 * What a signature answer may hold: a drawn image or a typed name. An answer
 * is `{ type: 'signature', signature: { method, name | file_id, signed_at } }`:
 *
 * - `typed`: the name, stored the way it is shown: trimmed, in Unicode form C,
 *   1 to SIGNATURE_NAME_MAX characters, without control, format (zero-width,
 *   bidirectional marks, the byte order mark, the soft hyphen), line and
 *   paragraph separator, surrogate, private-use or unassigned characters, nor
 *   the invisible fillers (Hangul fillers, blank braille); with at least one
 *   letter or digit, and no more than four combining marks in a row;
 * - `drawn`: the id of the PNG the browser made. The image itself travels as a
 *   file part of the submission and is kept as a private stored file, never in
 *   the answer.
 *
 * `signed_at` is stamped by the server; the browser never sends one. This
 * records a drawn or typed name: it does not check who signed. The server's
 * twin: common `signature.py` and answer_validation `signature_problem`.
 */

export const SIGNATURE_NAME_MAX = 100;
/** The font a typed signature is shown in: an italic serif every device has, so no font is downloaded (and no request leaves the page) for it. The name is always also plain text. */
export const TYPED_SIGNATURE_FONT = 'Georgia, "Times New Roman", serif';
export type SignatureMethod = 'drawn' | 'typed';
export const SIGNATURE_METHODS: ReadonlyArray<SignatureMethod> = ['drawn', 'typed'];

export interface SignatureValue {
    method?: string;
    file_id?: string;
    name?: string;
    signed_at?: string;
    url?: string;
}

// Control (Cc), format (Cf: zero-width and bidirectional marks, the byte order mark, the soft hyphen), the line and
// paragraph separators (Zl, Zp), surrogate (Cs), private-use (Co) and unassigned (Cn) characters never belong in a name:
// they reverse or hide text in a view. Nor do the characters that draw nothing but count as letters or symbols: the
// Hangul fillers and the blank braille pattern (a name of them would look empty).
const FORBIDDEN = /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}\p{Cs}\p{Co}\p{Cn}\u115F\u1160\u3164\uFFA0\u2800]/u;
// A name holds at least one letter or digit, and never more than four combining marks in a row (they only stack up).
const LETTER_OR_DIGIT = /[\p{L}\p{N}]/u;
const STACKED_MARKS = /\p{M}{5,}/u;
// What Python's str.strip() removes (the server's notion of "trimmed"), not what JavaScript's trim() does (it also strips U+FEFF).
const PY_SPACE = '\\t\\n\\v\\f\\r \\x1c-\\x1f\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const EDGE_SPACE = new RegExp(`^[${PY_SPACE}]|[${PY_SPACE}]$`);
const PY_TRIM = new RegExp(`^[${PY_SPACE}]+|[${PY_SPACE}]+$`, 'g');
// The id of a drawn image is part of a storage key: a plain id only (the server's is_plain_image_id).
const PLAIN_ID = /^[A-Za-z0-9._-]{1,128}$/;

/** The number of characters (code points, as the server counts them) of a name. */
export const signatureNameLength = (value: string): number => Array.from(value).length;

/** Is `value` a well-formed typed name (the length is checked apart)? */
export function isSignatureName(value: unknown): value is string {
    return typeof value === 'string' && value !== '' && !EDGE_SPACE.test(value) && value.normalize('NFC') === value && !FORBIDDEN.test(value) && LETTER_OR_DIGIT.test(value) && !STACKED_MARKS.test(value);
}

/** What to store for what was typed: trimmed, in form C; undefined when that leaves nothing, or no well-formed name. */
export function normalisedName(typed: string): string | undefined {
    const text = typed.replace(PY_TRIM, '').normalize('NFC');
    return isSignatureName(text) ? text : undefined;
}

export const isPlainImageId = (value: unknown): value is string => typeof value === 'string' && PLAIN_ID.test(value) && value !== '.' && value !== '..';

/** A signature answer is `{ method, file_id | name, signed_at, url }`, all text; another shape is the server's "type" problem. */
export function signatureShape(value: any): value is SignatureValue {
    return (
        !!value &&
        typeof value === 'object' &&
        !Array.isArray(value) &&
        Object.keys(value).every((key) => ['method', 'file_id', 'name', 'signed_at', 'url'].includes(key)) &&
        Object.values(value).every((v) => v === undefined || v === null || typeof v === 'string')
    );
}

/** What no signature may break whatever the question says (server `signature_problem`); null when it breaks nothing. */
export function signatureProblem(value: SignatureValue): 'FORMAT' | 'TOO_LONG' | 'SIGNATURE_IMAGE' | null {
    if (value.method !== 'typed' && value.method !== 'drawn') return 'FORMAT';
    if (value.method === 'typed') {
        if (value.file_id) return 'FORMAT';
        if (!isSignatureName(value.name)) return 'FORMAT';
        return signatureNameLength(value.name) > SIGNATURE_NAME_MAX ? 'TOO_LONG' : null;
    }
    if (value.name) return 'FORMAT';
    return isPlainImageId(value.file_id) ? null : 'SIGNATURE_IMAGE';
}

/** The signature slot of an answer, if it has a well-formed one. */
export function answerSignature(answer: any): SignatureValue | undefined {
    const value = answer?.signature;
    return signatureShape(value) ? value : undefined;
}

/** Is this answer a signature, drawn or typed (well-formed enough to count)? */
export const isSigned = (answer: any): boolean => {
    const value = answer?.signature;
    return signatureShape(value) && signatureProblem(value) === null;
};

/** The typed name, or a marker for a drawn one: never the image or a link. Used by exports. */
export function signatureExportText(answer: any): string {
    const value = answerSignature(answer);
    if (value?.method === 'typed') return typeof value.name === 'string' ? value.name : '';
    return value?.method === 'drawn' ? '[drawn signature]' : '';
}
