/**
 * What a tags answer may hold: short free-entry labels. An answer is
 * `{ type: 'tags', tags: ['a', 'b'] }`. A tag is stored the way it is shown:
 * trimmed and not empty, without `,` or `;` (they separate tags in the input
 * and in an export) or control characters, at most TAG_LENGTH_MAX characters,
 * and no two tags the same ignoring case. At most TAGS_MAX tags. The server's
 * twin: common `tags.py`.
 */

/** Tags one answer may hold, and the characters of one tag (hard caps: a question's own limits can only be lower). */
export const TAGS_MAX = 30;
export const TAG_LENGTH_MAX = 40;

// , and ; separate tags; the C0 and C1 control characters, and the line and paragraph separators, never belong in one.
const FORBIDDEN = /[,;\x00-\x1f\x7f-\x9f\u2028\u2029]/;
// What Python's str.strip() removes (the server's notion of "trimmed"), not what JavaScript's trim() does (it also strips U+FEFF).
const PY_SPACE = '\\t\\n\\v\\f\\r \\x1c-\\x1f\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const EDGE_SPACE = new RegExp(`^[${PY_SPACE}]|[${PY_SPACE}]$`);

/** Is `value` a well-formed tag (not looking at its length or at the other tags)? */
export function isTag(value: unknown): value is string {
    return typeof value === 'string' && value !== '' && !EDGE_SPACE.test(value) && !FORBIDDEN.test(value);
}

/** What two tags are compared by: the text without case. */
export const tagKey = (value: string): string => value.toLowerCase();

/** The number of characters (code points, as the server counts them) of a tag. */
export const tagLength = (value: string): number => Array.from(value).length;

/** The position of the first tag that repeats an earlier one, or null. */
export function duplicateIndex(tags: ReadonlyArray<string>): number | null {
    const seen = new Set<string>();
    for (let index = 0; index < tags.length; index++) {
        const key = tagKey(tags[index]);
        if (seen.has(key)) return index;
        seen.add(key);
    }
    return null;
}

/** The tags as one cell of an export (`; ` between them). */
export const joinedTags = (tags: ReadonlyArray<string>): string => tags.join('; ');

/** The tags of an answer, as the list it holds (strings only), or undefined when it has none. */
export function answerTags(answer: any): string[] | undefined {
    const tags = answer?.tags;
    return Array.isArray(tags) ? tags.filter((tag): tag is string => typeof tag === 'string') : undefined;
}
