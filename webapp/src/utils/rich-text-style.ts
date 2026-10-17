/**
 * Style values of rich-text titles (backend services/rich_text.py, keep in
 * step). The title editor's textStyle mark carries a font size and a colour,
 * written into an inline style attribute when a title is rendered. Only the
 * formats the editor writes are kept:
 *
 * - font size: pixels, "24" or "24px" (the editor's steps are 12, 15, 16,
 *   24 and 32), from FONT_SIZE_MIN to FONT_SIZE_MAX;
 * - colour: #rgb, #rrggbb, rgb(r, g, b) or rgba(r, g, b, a).
 *
 * The edit operations refuse other values; a whole-form save and the
 * respondent page drop them.
 */
export const FONT_SIZE_MIN = 8;
export const FONT_SIZE_MAX = 96;
const FONT_SIZE = /^(\d{1,3}(?:\.\d{1,2})?)(?:px)?$/;
const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const RGB = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(\d(?:\.\d{1,3})?|\.\d{1,3})\s*)?\)$/;
const STYLE_ATTRS = ['fontSize', 'color'] as const;

export function isValidFontSize(value: unknown): boolean {
    if (typeof value !== 'string') return false;
    const match = FONT_SIZE.exec(value);
    return !!match && Number(match[1]) >= FONT_SIZE_MIN && Number(match[1]) <= FONT_SIZE_MAX;
}

export function isValidColor(value: unknown): boolean {
    if (typeof value !== 'string') return false;
    if (HEX.test(value)) return true;
    const match = RGB.exec(value);
    if (!match) return false;
    return [match[1], match[2], match[3]].every((part) => Number(part) <= 255) && (match[4] === undefined || Number(match[4]) <= 1);
}

/** Why a textStyle attribute value is not one the editor writes (backend `style_value_problem`). */
export function styleValueProblem(name: string, value: unknown): string | null {
    if (value === null || value === undefined) return null;
    if (name === 'fontSize' && !isValidFontSize(value)) return `A font size must be a number of pixels from ${FONT_SIZE_MIN} to ${FONT_SIZE_MAX}, like '16px'.`;
    if (name === 'color' && !isValidColor(value)) return 'A colour must be #rgb, #rrggbb, rgb(r, g, b) or rgba(r, g, b, a).';
    return null;
}

/** A copy of a rich-text document without the font sizes and colours the editor never writes. */
export function sanitiseRichText<T>(document: T): T {
    const walk = (node: any): any => {
        if (Array.isArray(node)) return node.map(walk);
        if (!node || typeof node !== 'object') return node;
        const copy: any = { ...node };
        if (Array.isArray(node.marks)) {
            copy.marks = node.marks.map((mark: any) => {
                if (!mark || mark.type !== 'textStyle' || !mark.attrs || typeof mark.attrs !== 'object') return mark;
                const attrs = { ...mark.attrs };
                STYLE_ATTRS.forEach((name) => {
                    if (name in attrs && styleValueProblem(name, attrs[name])) delete attrs[name];
                });
                return { ...mark, attrs };
            });
        }
        if (Array.isArray(node.content)) copy.content = node.content.map(walk);
        return copy;
    };
    return walk(document);
}
