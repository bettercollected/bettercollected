/**
 * Shared vocabulary of the ops engine: errors, limits, field type sets and
 * read-only lookups on a plain (non-draft) form document.
 *
 * Mirrors the module-level helpers of `backend/app/services/ai/ops.py`; the
 * messages are the backend's, word for word, so that a result reads the same
 * wherever the batch was applied.
 */
import { FieldTypes } from '@app/models/dtos/form';
import { REPEAT_CHILD_FIELD_TYPES } from '@app/utils/repeating-groups';

import type { FormDoc, FormField } from './types';

/** A single operation failed; the batch continues with the next op. */
export class OpError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'OpError';
    }
}

/** An op would take the form past MAX_PAGES / MAX_FIELDS: the rest of the batch is not applied. */
export class SizeLimitReached extends OpError {}

// common/form_spec/models.py
export const MAX_PAGES = 200;
export const MAX_FIELDS = 2000;
export const PATTERN_MAX_LENGTH = 200;
// ops.py
export const MAX_NEW_PAGE_FIELDS = 200;
export const MAX_NEW_GROUP_FIELDS = 100;
export const MAX_OPS_PER_BATCH = 200;
// common/models/standard_form.py
export const DATE_RULES_MAX = 5;
export const WHY_WE_ASK_MAX_LENGTH = 280;
export const SECTION_TITLE_MAX_LENGTH = 120;
export const LABEL_MAX_LENGTH = 120;
export const REPEAT_MAX_ITEMS_LIMIT = 50;

export const SIZE_LIMIT_SKIPPED = "Not applied: an earlier operation reached the form's size limit.";
export const JUMP_TARGET_SUBMIT = '__SUBMIT__';
export const REF_PREFIX = '$ref:';
export const REF_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
/** Keys whose values may be a client reference (`"$ref:<name>"`). */
export const REF_ID_KEYS = new Set(['pageId', 'fieldId', 'groupId', 'afterFieldId', 'toPageId', 'toGroupId', 'childFieldId', 'target']);

/** Field types an op may create (backend ADDABLE_FIELD_TYPES). */
export const ADDABLE_FIELD_TYPES = new Set<string>([
    FieldTypes.SHORT_TEXT,
    FieldTypes.LONG_TEXT,
    FieldTypes.EMAIL,
    FieldTypes.NUMBER,
    FieldTypes.LINK,
    FieldTypes.PHONE_NUMBER,
    FieldTypes.DATE,
    FieldTypes.YES_NO,
    FieldTypes.MULTIPLE_CHOICE,
    FieldTypes.DROP_DOWN,
    FieldTypes.RATING,
    FieldTypes.LINEAR_RATING,
    FieldTypes.FILE_UPLOAD,
    FieldTypes.TEXT,
    FieldTypes.CALCULATED
]);
export const CHOICE_FIELD_TYPES = new Set<string>([FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN]);
export const RATING_FIELD_TYPES = new Set<string>([FieldTypes.RATING, FieldTypes.LINEAR_RATING]);
export const REPEAT_CHILD_TYPES = new Set<string>(REPEAT_CHILD_FIELD_TYPES);
/**
 * Types staff can fill in as internal fields (backend INTERNAL_CAPABLE_TYPES;
 * the webapp's twin, utils/internal-fields.ts, pulls in rendering code, so
 * the list is repeated here).
 */
export const INTERNAL_CAPABLE_TYPES = new Set<string>([
    FieldTypes.SHORT_TEXT,
    FieldTypes.LONG_TEXT,
    FieldTypes.NUMBER,
    FieldTypes.DATE,
    FieldTypes.EMAIL,
    FieldTypes.LINK,
    FieldTypes.PHONE_NUMBER,
    FieldTypes.YES_NO,
    FieldTypes.MULTIPLE_CHOICE,
    FieldTypes.DROP_DOWN
]);

export const INTERNAL_IN_GROUP_MESSAGE = 'Internal fields cannot be placed inside a repeating group — staff fill them in once per submission, not per item.';

/** Python's `sorted(...)` of plain ASCII strings, joined like the backend's messages. */
export const sortedList = (values: Iterable<string>) => [...values].sort().join(', ');

export const isSlide = (field: FormField | undefined | null): boolean => !!field && field.type === FieldTypes.SLIDE;

export const isRepeatingGroup = (field: FormField | undefined | null): boolean => !!field && field.type === FieldTypes.GROUP && field.properties != null && field.properties.repeat != null;

export const childrenOf = (field: FormField | undefined | null): FormField[] => (field?.properties?.fields as FormField[] | undefined) ?? [];

/** A question's title as the messages show it (backend `_title_text`). */
export function titleText(field: FormField): string {
    if (typeof field.title === 'string' && field.title.trim()) return field.title.trim();
    return field.id || 'untitled';
}

/** The question pages, in order. */
export function pagesOf(doc: FormDoc): FormField[] {
    return (doc.fields ?? []).filter(isSlide);
}

/** Where a page or question sits: indexes into the nested `fields` arrays. */
export interface PageLocation {
    page: FormField;
    /** Position of the page in `doc.fields`. */
    pos: number;
    /** 1-based number among the question pages. */
    number: number;
}

export function findPage(doc: FormDoc, pageId: string): PageLocation {
    const fields = doc.fields ?? [];
    let number = 0;
    for (let pos = 0; pos < fields.length; pos++) {
        const page = fields[pos];
        if (!isSlide(page)) continue;
        number++;
        if (page.id === pageId) return { page, pos, number };
    }
    throw new OpError(`Page '${pageId}' was not found — it may have been removed.`);
}

export interface FieldLocation {
    page: FormField;
    /** Position of the page in `doc.fields`. */
    pagePos: number;
    /** The repeating group the question is in, or null for a page question. */
    parent: FormField | null;
    /** Position of that group among the page's questions. */
    parentPos: number;
    field: FormField;
    /** Position in its container (the page's or the group's questions). */
    position: number;
    container: FormField[];
}

/** A page question or a repeating group's question, by id (backend `_locate_field`). */
export function locateField(doc: FormDoc, fieldId: string): FieldLocation {
    const found = tryLocateField(doc, fieldId);
    if (!found) throw new OpError(`Field '${fieldId}' was not found — it may have been removed.`);
    return found;
}

export function tryLocateField(doc: FormDoc, fieldId: string): FieldLocation | null {
    const top = doc.fields ?? [];
    for (let pagePos = 0; pagePos < top.length; pagePos++) {
        const page = top[pagePos];
        if (!isSlide(page)) continue;
        const fields = childrenOf(page);
        for (let position = 0; position < fields.length; position++) {
            const field = fields[position];
            if (field.id === fieldId) return { page, pagePos, parent: null, parentPos: -1, field, position, container: fields };
            if (isRepeatingGroup(field)) {
                const children = childrenOf(field);
                for (let childPos = 0; childPos < children.length; childPos++) {
                    if (children[childPos].id === fieldId) return { page, pagePos, parent: field, parentPos: position, field: children[childPos], position: childPos, container: children };
                }
            }
        }
    }
    return null;
}

export function findGroup(doc: FormDoc, groupId: string): FieldLocation {
    const location = locateField(doc, groupId);
    if (location.parent !== null || !isRepeatingGroup(location.field)) throw new OpError(`'${titleText(location.field)}' is not a repeating group.`);
    return location;
}

/** `field` and every field nested in it, breadth first (backend `_subtree`). */
export function subtree(field: FormField): FormField[] {
    const found: FormField[] = [];
    const pending = [field];
    while (pending.length) {
        const item = pending.shift()!;
        found.push(item);
        pending.push(...childrenOf(item));
    }
    return found;
}

export const subtreeIds = (field: FormField) => new Set(subtree(field).map((f) => f.id));

/** Fields of a list, nested ones (group questions) included (common `count_fields`). */
export function countFields(fields: FormField[] | undefined | null): number {
    let total = 0;
    for (const field of fields ?? []) {
        total += 1;
        const children = field?.properties?.fields as FormField[] | undefined;
        if (children?.length) total += countFields(children);
    }
    return total;
}

/** (question pages, fields on them, group questions included). */
export function formSize(doc: FormDoc): [number, number] {
    const pages = pagesOf(doc);
    let fields = 0;
    for (const page of pages) fields += countFields(page.properties?.fields);
    return [pages.length, fields];
}

/** Why `(pages, fields)` is too big, unless it did not grow. */
export function sizeProblem(pages: number, fields: number, before: [number, number]): string | null {
    if (pages > MAX_PAGES && pages > before[0]) return `A form can have at most ${MAX_PAGES} pages; this would make ${pages}.`;
    if (fields > MAX_FIELDS && fields > before[1]) return `A form can have at most ${MAX_FIELDS} fields in all; this would make ${fields}.`;
    return null;
}

export function ensureCanBeInternal(type: string): void {
    if (!INTERNAL_CAPABLE_TYPES.has(type)) {
        throw new OpError(`'${type}' fields can't be internal — staff fill internal fields in from the dashboard (text, number, date, email, link, phone, yes/no, choice and dropdown).`);
    }
}

export function checkChildType(type: string, internal?: boolean | null): void {
    if (type === FieldTypes.GROUP) throw new OpError('Repeating groups cannot contain another group.');
    if (internal) throw new OpError(INTERNAL_IN_GROUP_MESSAGE);
    if (!REPEAT_CHILD_TYPES.has(type)) throw new OpError(`A '${type}' question cannot be placed inside a repeating group (allowed: ${sortedList(REPEAT_CHILD_TYPES)}).`);
}

/** Python's `str(value)` for the values messages quote. */
export function pyStr(value: unknown): string {
    if (value === null || value === undefined) return 'None';
    if (value === true) return 'True';
    if (value === false) return 'False';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
}

/** Python's `format(value, 'g')`: six significant digits, no trailing zeros. */
export function pyG(value: number): string {
    if (!Number.isFinite(value)) return Number.isNaN(value) ? 'nan' : value > 0 ? 'inf' : '-inf';
    if (value === 0) return Object.is(value, -0) ? '-0' : '0';
    const exponent = Math.floor(Math.log10(Math.abs(Number(value.toPrecision(6)))));
    if (exponent < -4 || exponent >= 6) {
        const [mantissa, exp] = value.toExponential(5).split('e');
        const trimmed = mantissa.includes('.') ? mantissa.replace(/0+$/, '').replace(/\.$/, '') : mantissa;
        const sign = exp.startsWith('-') ? '-' : '+';
        const digits = exp.replace(/^[+-]/, '').padStart(2, '0');
        return `${trimmed}e${sign}${digits}`;
    }
    const fixed = value.toFixed(Math.max(0, 5 - exponent));
    return fixed.includes('.') ? fixed.replace(/0+$/, '').replace(/\.$/, '') : fixed;
}

/** Length in code points, as Python's `len` counts a string. */
export const pyLen = (text: string) => [...text].length;

/** Python's `" ".join(text.split())`. */
export const collapseWhitespace = (text: string) => text.split(/\s+/u).filter(Boolean).join(' ');

/** Plain JSON copy (the ops and documents are JSON). */
export function clone<T>(value: T): T {
    return value === undefined ? value : (JSON.parse(JSON.stringify(value)) as T);
}

/** Deep equality of JSON values; `undefined` and `null` object entries count as absent. */
export function jsonEqual(a: any, b: any): boolean {
    if (a === b) return true;
    if (a === null || b === null || a === undefined || b === undefined) return (a ?? null) === (b ?? null);
    if (typeof a !== 'object' || typeof b !== 'object') return false;
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    if (Array.isArray(a)) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) if (!jsonEqual(a[i], b[i])) return false;
        return true;
    }
    for (const key of Object.keys(a)) if (!jsonEqual(a[key], b[key])) return false;
    for (const key of Object.keys(b)) if (!(key in a) && b[key] != null) return false;
    return true;
}

/** Every field type the backend knows (common StandardFormFieldType). */
export const KNOWN_FIELD_TYPES = new Set<string>(
    'slide,date,short_text,long_text,multiple_choice,opinion_scale,ranking,rating,dropdown,matrix,tabular_input,file_upload,group,email,payment,statement,page_break,calculated,hidden,conditional,h1,h2,h3,h4,h5,p,strong,divider,markdown,input_short_text,input_long_text,input_markdown,input_multiple_choice,input_multiselect,input_checkboxes,input_email,input_number,input_phone_number,input_link,input_date,input_time,input_date_range,input_time_range,input_datetime_range,input_dropdown,input_rating,input_linear_scale,input_template_button,input_file_upload,input_ranking,input_matrix,text,yes_no,url,linear_rating,phone_number,number,VIDEO_CONTENT,IMAGE_CONTENT,date_input,email_input,number_input,short_text_input,long_text_input,multiple_choice_input,ranking_input,rating_input,drop_down_input,media_input,matrix_row_input'.split(
        ','
    )
);

/** `value` without null entries, deeply (what the backend stores and sends back). */
export function withoutNulls<T>(value: T): T {
    if (Array.isArray(value)) return value.map(withoutNulls) as T;
    if (value && typeof value === 'object') {
        const out: Record<string, any> = {};
        for (const [key, item] of Object.entries(value)) if (item !== null && item !== undefined) out[key] = withoutNulls(item);
        return out as T;
    }
    return value;
}
