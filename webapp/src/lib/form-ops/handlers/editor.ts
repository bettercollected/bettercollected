/**
 * Editor ops: lossless, id-addressed edits the builder makes (whole
 * questions and pages with their ids, page and welcome page settings,
 * hidden fields, logo settings, choices by id). Not offered to the AI or the
 * API. Backend twin: "Editor ops: handlers" in ops.py — checked like a
 * whole-form save (ids unique in the form, size limits, image addresses,
 * answer patterns, repeating group rules).
 */
import { FieldTypes } from '@app/models/dtos/form';

import { dateRuleProblems, questionsWithScope } from '../date-rules';
import { IMAGE_URL_ERROR, firstPartyImageUrl, formImageUrls } from '../images';
import {
    KNOWN_FIELD_TYPES,
    OpError,
    REPEAT_CHILD_TYPES,
    SECTION_TITLE_MAX_LENGTH,
    checkChildType,
    childrenOf,
    clone,
    countFields,
    ensureCanBeInternal,
    findGroup,
    findPage,
    isRepeatingGroup,
    isSlide,
    locateField,
    pagesOf,
    pyLen,
    subtree,
    subtreeIds,
    titleText,
    withoutNulls
} from '../model';
import type { AddChoiceOp, ApplyOptions, FormDoc, FormField, InsertFieldOp, InsertPageOp, MoveChoiceOp, RemoveChoiceOp, ReplaceFieldOp, SetChoiceOp, SetHiddenFieldsOp, UpdateLogoOp, UpdatePageOp, UpdateWelcomePageOp } from '../types';
import { type Handler, type OpContext, draftField, droppedHiddenReferencesNote, droppedReferencesNote, ensureProperties, insertedAt, setFields, setKey } from './context';
import { checkedPattern, repeatProblems } from './fields';

/** A rich-text title, serialised: at most this many characters, nested at most this deep. */
export const TITLE_JSON_MAX_CHARS = 64 * 1024;
export const TITLE_JSON_MAX_DEPTH = 64;
// Hidden fields: any names a whole-form save accepts, within these limits.
export const HIDDEN_FIELDS_MAX = 100;
export const HIDDEN_FIELD_NAME_MAX_LENGTH = 200;
const LOGO_ALT_MAX_LENGTH = 150;
const CHOICE_EDIT_TYPES = new Set<string>([FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN, FieldTypes.RANKING]);
const THEME_KEYS = ['title', 'primary', 'secondary', 'tertiary', 'accent'];

function jsonDepth(value: unknown): number {
    let depth = 0;
    const pending: Array<[unknown, number]> = [[value, 1]];
    while (pending.length) {
        const [item, level] = pending.pop()!;
        if (item && typeof item === 'object') {
            depth = Math.max(depth, level);
            for (const child of Array.isArray(item) ? item : Object.values(item)) pending.push([child, level + 1]);
        }
    }
    return depth;
}

type AttrRule = 'int' | 'int?' | 'str' | 'str?';
const STR: AttrRule = 'str?';
/**
 * What a rich-text title may hold: the node and mark types (with their
 * attributes) of the builder's title editor (backend TITLE_NODES and
 * TITLE_MARKS). Respondent pages render titles with that schema.
 */
export const TITLE_NODES: Record<string, Record<string, AttrRule>> = {
    doc: {},
    paragraph: {},
    text: {},
    heading: { level: 'int' },
    hardBreak: {},
    blockquote: {},
    bulletList: {},
    orderedList: { start: 'int?', type: STR },
    listItem: {},
    codeBlock: { language: STR },
    horizontalRule: {},
    answerPipe: { kind: 'str', pipeKey: STR, label: STR, fallback: STR }
};
export const TITLE_MARKS: Record<string, Record<string, AttrRule>> = { bold: {}, italic: {}, underline: {}, strike: {}, code: {}, textStyle: { fontSize: STR, color: STR } };
const PIPE_KINDS = new Set(['field', 'hidden', 'group']);
const NODE_KEYS = new Set(['type', 'attrs', 'content', 'marks', 'text']);

function attrMatches(value: unknown, rule: AttrRule): boolean {
    if (typeof value === 'boolean') return false;
    if (value === null) return rule.endsWith('?');
    return rule.startsWith('int') ? typeof value === 'number' && Number.isInteger(value) : typeof value === 'string';
}

function attrsProblem(what: string, attrs: unknown, allowed: Record<string, AttrRule>): string | null {
    if (attrs === undefined || attrs === null) return null;
    if (typeof attrs !== 'object' || Array.isArray(attrs)) return `The attributes of a '${what}' must be an object.`;
    for (const [key, value] of Object.entries(attrs)) {
        if (!(key in allowed)) return `A '${what}' cannot have the attribute '${key}'.`;
        if (!attrMatches(value, allowed[key])) return `The attribute '${key}' of a '${what}' has the wrong type.`;
    }
    return null;
}

/** Why `title` is not a document the title editor can render, if so (backend `_rich_text_problem`). */
function richTextProblem(title: Record<string, any>): string | null {
    if (title.type !== 'doc') return "A rich-text title must be a document (type 'doc').";
    const pending: any[] = [title];
    while (pending.length) {
        const node = pending.pop();
        if (!node || typeof node !== 'object' || Array.isArray(node)) return 'A rich-text title may only hold nodes (objects).';
        const kind = node.type;
        if (typeof kind !== 'string' || !(kind in TITLE_NODES)) return `A rich-text title cannot hold a '${kind ?? 'None'}' node.`;
        const unknown = Object.keys(node)
            .filter((key) => !NODE_KEYS.has(key))
            .sort();
        if (unknown.length) return `A '${kind}' node cannot have '${unknown[0]}'.`;
        const problem = attrsProblem(kind, node.attrs, TITLE_NODES[kind]);
        if (problem) return problem;
        const level = node.attrs?.level ?? 1;
        if (kind === 'heading' && !(level >= 1 && level <= 6)) return "A heading's level must be 1 to 6.";
        if (kind === 'answerPipe' && !PIPE_KINDS.has(node.attrs?.kind ?? 'field')) return "An answer pipe's kind must be field, hidden or group.";
        if (kind === 'text') {
            if (typeof node.text !== 'string' || !node.text) return 'A text node needs some text.';
        } else if ('text' in node) return `A '${kind}' node cannot hold text.`;
        const marks = node.marks;
        if (marks !== undefined && marks !== null) {
            if (!Array.isArray(marks)) return 'Marks must be a list.';
            for (const mark of marks) {
                const name = mark && typeof mark === 'object' && !Array.isArray(mark) ? mark.type : undefined;
                if (typeof name !== 'string' || !(name in TITLE_MARKS)) return `A rich-text title cannot use a '${name ?? 'None'}' mark.`;
                if (Object.keys(mark).some((key) => key !== 'type' && key !== 'attrs')) return `A '${name}' mark can only have attributes.`;
                const markProblem = attrsProblem(name, mark.attrs, TITLE_MARKS[name]);
                if (markProblem) return markProblem;
            }
        }
        const content = node.content;
        if (content !== undefined && content !== null) {
            if (!Array.isArray(content) || kind === 'text') return `The content of a '${kind}' node is not valid.`;
            pending.push(...content);
        }
    }
    return null;
}

/**
 * A rich-text title must stay small and hold only what the title editor
 * holds (backend `_check_title`).
 */
export function checkTitle(title: unknown): void {
    if (!title || typeof title !== 'object' || Array.isArray(title)) return;
    if (jsonDepth(title) > TITLE_JSON_MAX_DEPTH) throw new OpError(`A rich-text title can be nested at most ${TITLE_JSON_MAX_DEPTH} levels deep.`);
    const size = pyLen(JSON.stringify(title));
    if (size > TITLE_JSON_MAX_CHARS) throw new OpError(`A rich-text title can be at most ${TITLE_JSON_MAX_CHARS} characters long as JSON (this one has ${size}).`);
    const problem = richTextProblem(title as Record<string, any>);
    if (problem) throw new OpError(problem);
}

function formIds(doc: FormDoc): Set<string> {
    const ids = new Set<string>();
    for (const item of doc.fields ?? []) for (const f of subtree(item)) if (f.id) ids.add(f.id);
    return ids;
}

/** Every id of `item` is given and unused in the form, apart from those of what it replaces. */
function checkNewIds(doc: FormDoc, item: FormField, replaced: Set<string> = new Set()): void {
    const taken = formIds(doc);
    const seen = new Set<string>();
    for (const field of subtree(item)) {
        if (typeof field.id !== 'string' || !field.id.trim()) throw new OpError('Every page and question needs an id.');
        if ((taken.has(field.id) && !replaced.has(field.id)) || seen.has(field.id)) throw new OpError(`The id '${field.id}' is already used in this form.`);
        seen.add(field.id);
        const choiceIds = (field.properties?.choices ?? []).map((c: any) => c.id);
        if (new Set(choiceIds).size !== choiceIds.length) throw new OpError(`The choices of '${titleText(field)}' need unique ids.`);
    }
}

/** The address to store for one image: first-party, or already on the form. */
function editorImage(url: unknown, keep: Set<string>, options: ApplyOptions): any {
    if (typeof url !== 'string' || !url.trim()) return url;
    const stored = firstPartyImageUrl(url, options);
    if (stored !== null) return stored;
    if (keep.has(url.trim())) return url;
    throw new OpError(IMAGE_URL_ERROR);
}

function editorAttachment(attachment: any, keep: Set<string>, options: ApplyOptions): void {
    if (attachment && attachment.type === 'image') setKey(attachment, 'href', editorImage(attachment.href, keep, options));
}

function editorTheme(theme: any, keep: Set<string>, options: ApplyOptions): void {
    if (theme?.background) setKey(theme.background, 'imageUrl', editorImage(theme.background.imageUrl, keep, options));
}

/**
 * Model checks a whole-form save makes on one field and those nested in it
 * (StandardFormFieldCamelModel): field-level errors as "loc: message", then
 * the field's own repeating group and date rule checks.
 */
function modelProblems(field: any, loc: string): string[] {
    const errors: string[] = [];
    const at = (path: string) => (loc ? `${loc}.${path}` : path);
    (field.properties?.fields ?? []).forEach((child: any, i: number) => errors.push(...modelProblems(child, at(`properties.fields.${i}`))));
    const properties = field.properties ?? {};
    if (properties.theme) for (const key of THEME_KEYS) if (typeof properties.theme[key] !== 'string') errors.push(`${at(`properties.theme.${key}`)}: Field required`);
    if (properties.colSpan != null && (properties.colSpan < 1 || properties.colSpan > 12)) errors.push(`${at('properties.colSpan')}: Input should be ${properties.colSpan < 1 ? 'greater than or equal to 1' : 'less than or equal to 12'}`);
    if (properties.repeat) {
        const problem = repeatProblems(properties.repeat);
        if (problem) errors.push(`${at('properties.repeat')}: ${problem.startsWith('Input') || problem.startsWith('String') ? problem : `Value error, ${problem}`}`);
    }
    // a calculated field's format (common CalculationFormat)
    const format = properties.format;
    if (format && typeof format === 'object') {
        if (format.style != null && !['number', 'currency', 'percent', 'text'].includes(format.style)) errors.push(`${at('properties.format.style')}: Input should be 'number', 'currency', 'percent' or 'text'`);
        if (format.decimals != null && (format.decimals < 0 || format.decimals > 6)) errors.push(`${at('properties.format.decimals')}: Input should be ${format.decimals < 0 ? 'greater than or equal to 0' : 'less than or equal to 6'}`);
        if (format.currency != null && !/^[A-Z]{3}$/.test(String(format.currency))) errors.push(`${at('properties.format.currency')}: String should match pattern '^[A-Z]{3}$'`);
    }
    (properties.dateRules ?? []).forEach((rule: any, i: number) => {
        if (rule?.target === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(String(rule.date ?? ''))) errors.push(`${at(`properties.dateRules.${i}`)}: Value error, A date rule needs a date written as YYYY-MM-DD.`);
        if (rule?.target === 'field' && (typeof rule.fieldId !== 'string' || !rule.fieldId.trim())) errors.push(`${at(`properties.dateRules.${i}`)}: Value error, A date rule on another question needs its id.`);
    });
    if (errors.length) return errors;
    const own = ownModelProblem(field);
    return own ? [loc ? `${loc}: Value error, ${own}` : own] : [];
}

/** The model validator of a stored field (common `check_repeating_group_structure`, `check_field_date_rules`). */
function ownModelProblem(field: any): string | null {
    const properties = field.properties;
    if (properties?.repeat != null) {
        if (field.type !== FieldTypes.GROUP) return 'Only a group field can repeat.';
        if (field.internal) return 'A repeating group cannot be an internal field.';
        const seen = new Set<string>();
        for (const child of properties.fields ?? []) {
            if (child.type === FieldTypes.GROUP) return 'Repeating groups cannot contain another group.';
            if (!REPEAT_CHILD_TYPES.has(child.type)) return `A '${child.type ?? 'None'}' question cannot be placed inside a repeating group.`;
            if (child.internal) return 'Internal fields cannot be placed inside a repeating group.';
            if (child.id && seen.has(child.id)) return 'Questions inside a repeating group need unique ids.';
            seen.add(child.id);
        }
    }
    const rules = properties?.dateRules;
    if (rules?.length) {
        if (field.type !== FieldTypes.DATE) return 'Only date questions can have date rules.';
        for (const rule of rules) if (field.id && rule.fieldId === field.id) return 'A date rule cannot compare a question with itself.';
    }
    return null;
}

/** A question or page as the editor sends it, checked the way a whole-form save checks it (backend `_editor_item`). */
function editorItem(raw: unknown, ctx: OpContext, page: boolean): FormField {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new OpError('Input should be a valid dictionary');
    const item = withoutNulls(clone(raw)) as FormField;
    for (const field of subtree(item)) {
        // an unknown type is no type
        if (field.type != null && !KNOWN_FIELD_TYPES.has(field.type)) delete (field as any).type;
        for (const rule of field.properties?.dateRules ?? []) {
            if (rule.target === 'date') delete rule.fieldId;
            else if (rule.target === 'field') delete rule.date;
            else {
                delete rule.date;
                delete rule.fieldId;
            }
        }
    }
    const problems = modelProblems(item, '');
    if (problems.length) throw new OpError(problems.slice(0, 5).join('; '));
    const isPage = item.type === FieldTypes.SLIDE;
    if (page && !isPage) throw new OpError("insert_page needs a page: a field of type 'slide'.");
    if (!page && isPage) throw new OpError('A page is not a question: use insert_page or update_page.');
    const keep = formImageUrls(ctx.state);
    for (const field of subtree(item)) {
        if (field !== item && field.type === FieldTypes.SLIDE) throw new OpError('A page cannot be placed inside another page or question.');
        if (field.type == null) throw new OpError(`'${titleText(field)}' needs a type.`);
        checkTitle(field.title);
        const regex = field.validations?.regex;
        if (regex != null && regex.trim()) checkedPattern(regex);
        if (field.internal) ensureCanBeInternal(field.type);
        setKey(field, 'imageUrl', editorImage(field.imageUrl, keep, ctx.options));
        editorAttachment(field.attachment, keep, ctx.options);
        if (field.properties) {
            editorTheme(field.properties.theme, keep, ctx.options);
            for (const choice of field.properties.choices ?? []) editorAttachment((choice as any).attachment, keep, ctx.options);
        }
    }
    return item;
}

/** Reasons respondent logic depends on an internal field (backend `internal_logic_violations`). */
function internalLogicViolations(doc: FormDoc): string[] {
    const questions = questionsWithScope(doc.fields).map((q) => q.question);
    // the questions of other groups count too
    for (const question of [...questions]) if (question?.type === FieldTypes.GROUP && !isRepeatingGroup(question)) questions.push(...childrenOf(question));
    const internal = new Set(questions.filter((q) => q?.internal && q.id).map((q) => String(q.id)));
    if (!internal.size) return [];
    const problems: string[] = [];
    const check = (conditions: any[] | undefined, where: string) => {
        for (const condition of conditions ?? []) {
            const source = condition?.fieldId;
            if (source && internal.has(String(source))) problems.push(`${where} depends on internal field '${source}' — respondents never answer internal fields, so logic cannot use them.`);
        }
    };
    for (const field of doc.fields ?? []) for (const jump of field.properties?.jumps ?? []) check(jump.conditions, `A page jump on page '${field.id}'`);
    for (const question of questions) check(question?.properties?.logic?.conditions, `The visibility rule of '${question.id}'`);
    return problems;
}

/** The first problem a whole-form save would refuse in `after` that `before` did not have. */
function newProblem(before: FormDoc, after: FormDoc): string | null {
    const known = new Set(internalLogicViolations(before));
    for (const problem of internalLogicViolations(after)) if (!known.has(problem)) return problem;
    const knownRules = new Set(dateRuleProblems(before.fields));
    for (const problem of dateRuleProblems(after.fields)) if (!knownRules.has(problem)) return problem;
    return null;
}

/** A plain copy of `doc` (shallow, along the path) with the questions of a page or group replaced. */
function withList(doc: FormDoc, pagePos: number, groupPos: number | null, list: FormField[]): FormDoc {
    const fields = [...(doc.fields ?? [])];
    const page = fields[pagePos];
    if (groupPos === null) {
        fields[pagePos] = { ...page, properties: { ...page.properties, fields: list } };
    } else {
        const pageFields = [...childrenOf(page)];
        pageFields[groupPos] = { ...pageFields[groupPos], properties: { ...pageFields[groupPos].properties, fields: list } };
        fields[pagePos] = { ...page, properties: { ...page.properties, fields: pageFields } };
    }
    return { ...doc, fields };
}

function checkIndex(index: unknown): number {
    if (typeof index !== 'number' || !Number.isInteger(index)) throw new OpError('index: Input should be a valid integer');
    if (index < 0) throw new OpError('index: Input should be greater than or equal to 0');
    return index;
}

/** Draft of the page (`groupPos` null) or of the group at `groupPos` on it. */
function ownerDraft(ctx: OpContext, pagePos: number, groupPos: number | null): any {
    const page = ctx.draft.fields![pagePos];
    return groupPos === null ? page : page.properties!.fields![groupPos];
}

export const insertField: Handler<InsertFieldOp> = (ctx, op) => {
    const field = editorItem(op.field, ctx, false);
    checkNewIds(ctx.state, field);
    const index = checkIndex(op.index);
    let pagePos: number;
    let groupPos: number | null = null;
    let container: FormField[];
    let where: string;
    if (op.groupId != null) {
        const group = findGroup(ctx.state, op.groupId);
        if (op.pageId != null && group.page.id !== op.pageId) throw new OpError(`The group '${op.groupId}' is not on page '${op.pageId}'.`);
        checkChildType(field.type, field.internal);
        pagePos = group.pagePos;
        groupPos = group.position;
        container = childrenOf(group.field);
        where = `the group '${titleText(group.field)}'`;
    } else if (op.pageId != null) {
        const page = findPage(ctx.state, op.pageId);
        pagePos = page.pos;
        container = childrenOf(page.page);
        where = `page ${page.number}`;
    } else {
        throw new OpError('insert_field needs a pageId (or a groupId).');
    }
    const list = insertedAt(container, Math.min(index, container.length), field);
    const problem = newProblem(ctx.state, withList(ctx.state, pagePos, groupPos, list));
    if (problem) throw new OpError(problem);
    setFields(ownerDraft(ctx, pagePos, groupPos), list);
    ctx.noteCreated(field.id);
    return `Inserted '${titleText(field)}' (${field.type}) into ${where}`;
};

export const replaceField: Handler<ReplaceFieldOp> = (ctx, op) => {
    const field = editorItem(op.field, ctx, false);
    if (pagesOf(ctx.state).some((p) => p.id === field.id)) throw new OpError(`'${field.id}' is a page: change it with update_page.`);
    const location = locateField(ctx.state, field.id);
    checkNewIds(ctx.state, field, new Set(subtree(location.field).map((f) => f.id)));
    if (location.parent) checkChildType(field.type, field.internal);
    const list = location.container.map((f, i) => (i === location.position ? field : f));
    const groupPos = location.parent ? location.parentPos : null;
    const problem = newProblem(ctx.state, withList(ctx.state, location.pagePos, groupPos, list));
    if (problem) throw new OpError(problem);
    setFields(ownerDraft(ctx, location.pagePos, groupPos), list);
    const kept = subtreeIds(field);
    const gone = new Set([...subtreeIds(location.field)].filter((id) => !kept.has(id)));
    return `Replaced '${titleText(field)}'${droppedReferencesNote(ctx, gone)}`;
};

export const insertPage: Handler<InsertPageOp> = (ctx, op) => {
    const page = editorItem(op.page, ctx, true);
    checkNewIds(ctx.state, page);
    const index = checkIndex(op.index);
    const top = ctx.state.fields ?? [];
    const pages = pagesOf(ctx.state);
    const position = index >= pages.length ? top.length : top.indexOf(pages[index]);
    const fields = insertedAt(top, position, page);
    const problem = newProblem(ctx.state, { ...ctx.state, fields });
    if (problem) throw new OpError(problem);
    ctx.draft.fields = fields as any;
    ctx.noteCreated(page.id);
    return `Inserted a page with ${childrenOf(page).length} field(s) at position ${fields.filter(isSlide).indexOf(page) + 1}`;
};

const PAGE_PATCH_LABELS: Record<string, string> = { layout: 'layout', imageUrl: 'image', theme: 'theme', position: 'position', showQuestionNumbers: 'question numbers', sectionTitle: 'section title' };

function checkPatchKeys(patch: Record<string, any>, allowed: Record<string, unknown>): void {
    for (const key of Object.keys(patch)) if (!(key in allowed)) throw new OpError(`patch.${key}: Extra inputs are not permitted`);
}

export const updatePage: Handler<UpdatePageOp> = (ctx, op) => {
    const { page, pos, number } = findPage(ctx.state, op.pageId);
    const patch = (op.patch ?? {}) as Record<string, any>;
    checkPatchKeys(patch, PAGE_PATCH_LABELS);
    const given = Object.keys(PAGE_PATCH_LABELS).filter((key) => key in patch);
    if (!given.length) throw new OpError('The update contained no changes.');
    const keep = formImageUrls(ctx.state);
    // checked first: a refused value leaves the page as it was
    const imageUrl = given.includes('imageUrl') ? editorImage(patch.imageUrl, keep, ctx.options) : undefined;
    const theme = patch.theme != null ? withoutNulls(clone(patch.theme)) : undefined;
    if (theme) for (const key of THEME_KEYS) if (typeof theme[key] !== 'string') throw new OpError(`patch.theme.${key}: Field required`);
    editorTheme(theme, keep, ctx.options);
    let sectionTitle: string | undefined;
    if (given.includes('sectionTitle') && patch.sectionTitle != null) {
        sectionTitle = String(patch.sectionTitle).trim() || undefined;
        if (sectionTitle && pyLen(sectionTitle) > SECTION_TITLE_MAX_LENGTH) throw new OpError(`A section title can be at most ${SECTION_TITLE_MAX_LENGTH} characters.`);
    }
    const target = ctx.draft.fields![pos];
    if (page.properties == null) target.properties = { fields: [] };
    const properties = target.properties as Record<string, any>;
    if (given.includes('layout')) setKey(properties, 'layout', patch.layout);
    if (given.includes('imageUrl')) setKey(target, 'imageUrl', imageUrl || undefined);
    if (given.includes('theme')) setKey(properties, 'theme', theme);
    if (given.includes('position')) setKey(properties, 'position', patch.position == null ? undefined : withoutNulls(clone(patch.position)));
    if (given.includes('showQuestionNumbers')) setKey(properties, 'showQuestionNumbers', patch.showQuestionNumbers);
    if (given.includes('sectionTitle')) setKey(properties, 'sectionTitle', sectionTitle);
    return `Updated page ${number} (${given.map((key) => PAGE_PATCH_LABELS[key]).join(', ')})`;
};

const WELCOME_KEYS: Record<string, string> = { title: 'title', description: 'description', layout: 'layout', imageUrl: 'image url', buttonText: 'button text' };

/**
 * Sets the welcome page's keys. A welcome page left with no key at all is
 * removed (the backend keeps an empty one; both read the same).
 */
export const updateWelcomePage: Handler<UpdateWelcomePageOp> = (ctx, op) => {
    const patch = (op.patch ?? {}) as Record<string, any>;
    checkPatchKeys(patch, WELCOME_KEYS);
    const given = Object.keys(WELCOME_KEYS).filter((key) => key in patch);
    if (!given.length) throw new OpError('The update contained no changes.');
    const imageUrl = given.includes('imageUrl') ? editorImage(patch.imageUrl, formImageUrls(ctx.state), ctx.options) || undefined : undefined;
    if (ctx.draft.welcomePage == null) ctx.draft.welcomePage = {};
    const welcome = ctx.draft.welcomePage as Record<string, any>;
    for (const key of given) setKey(welcome, key, key === 'imageUrl' ? imageUrl : patch[key]);
    if (!Object.keys(welcome).length) delete ctx.draft.welcomePage;
    return `Updated the welcome page (${given.map((key) => WELCOME_KEYS[key]).join(', ')})`;
};

/**
 * The hidden fields as a whole, named as a whole-form save takes them (the
 * builder's editor only lets a creator type URL-safe names, but an older
 * form may hold others and stays editable); pipes of names no longer listed
 * go. An empty list removes the key (the backend keeps `[]`; both read the
 * same).
 */
export const setHiddenFields: Handler<SetHiddenFieldsOp> = (ctx, op) => {
    const names = op.names;
    if (!Array.isArray(names) || names.some((n) => typeof n !== 'string')) throw new OpError('names: Input should be a valid list of strings');
    if (names.length > HIDDEN_FIELDS_MAX) throw new OpError(`A form can have at most ${HIDDEN_FIELDS_MAX} hidden fields.`);
    for (const name of names) if (pyLen(name) > HIDDEN_FIELD_NAME_MAX_LENGTH) throw new OpError(`A hidden field name can be at most ${HIDDEN_FIELD_NAME_MAX_LENGTH} characters.`);
    const kept = new Set(names);
    const gone = new Set((ctx.state.hiddenFields ?? []).filter((name) => !kept.has(name)));
    if (names.length) ctx.draft.hiddenFields = [...names];
    else delete ctx.draft.hiddenFields;
    return `Set ${names.length} hidden field(s)${droppedHiddenReferencesNote(ctx, gone)}`;
};

// in the sorted order of the backend's own names (alt, position, use_workspace_logo)
const LOGO_KEYS: Record<string, [string, string]> = { alt: ['logoAlt', 'alt text'], position: ['logoPosition', 'position'], useWorkspaceLogo: ['useWorkspaceLogo', 'workspace logo'] };

export const updateLogo: Handler<UpdateLogoOp> = (ctx, op) => {
    const given = Object.keys(LOGO_KEYS).filter((key) => key in op);
    if (!given.length) throw new OpError('The update contained no changes.');
    if (op.position != null && !['auto', 'left', 'center'].includes(op.position)) throw new OpError("position: Input should be 'auto', 'left' or 'center'");
    if (typeof op.alt === 'string' && pyLen(op.alt) > LOGO_ALT_MAX_LENGTH) throw new OpError(`The logo's alt text can be at most ${LOGO_ALT_MAX_LENGTH} characters.`);
    for (const key of given) setKey(ctx.draft, LOGO_KEYS[key][0], (op as Record<string, any>)[key]);
    return `Updated the logo settings (${given.map((key) => LOGO_KEYS[key][1]).join(', ')})`;
};

// ---------------------------------------------------------------------------
// Choices by id
// ---------------------------------------------------------------------------

function choiceField(ctx: OpContext, fieldId: string, change: boolean) {
    const location = locateField(ctx.state, fieldId);
    const { field } = location;
    if (field.type === FieldTypes.YES_NO && change) throw new OpError('Yes/No choices are fixed.');
    if (!CHOICE_EDIT_TYPES.has(field.type) && field.type !== FieldTypes.YES_NO) throw new OpError(`'${titleText(field)}' is a ${field.type || 'unknown'} question: it has no choices.`);
    const properties = ensureProperties(draftField(ctx.draft, location));
    if (properties.choices == null) properties.choices = [];
    return { field, choices: (field.properties?.choices ?? []) as any[], target: properties as any };
}

function choicePosition(field: FormField, choices: any[], choiceId: string): number {
    const position = choices.findIndex((c) => c.id === choiceId);
    if (position < 0) throw new OpError(`'${titleText(field)}' has no choice '${choiceId}'.`);
    return position;
}

export const setChoice: Handler<SetChoiceOp> = (ctx, op) => {
    const { field, choices, target } = choiceField(ctx, op.fieldId, true);
    const position = choicePosition(field, choices, op.choiceId);
    target.choices = choices.map((c, i) => (i === position ? withoutNulls({ ...c, value: op.value }) : c));
    return `Changed a choice of '${titleText(field)}'`;
};

export const addChoice: Handler<AddChoiceOp> = (ctx, op) => {
    const { field, choices, target } = choiceField(ctx, op.fieldId, true);
    const raw = op.choice;
    if (!raw || typeof raw.id !== 'string') throw new OpError('choice.id: Field required');
    if (!raw.id.trim()) throw new OpError('A choice needs an id.');
    if (choices.some((c) => c.id === raw.id)) throw new OpError(`'${titleText(field)}' already has a choice '${raw.id}'.`);
    const choice: Record<string, any> = withoutNulls({ id: raw.id, value: raw.value, ref: raw.ref, label: raw.label, attachment: raw.attachment == null ? undefined : clone(raw.attachment) });
    editorAttachment(choice.attachment, formImageUrls(ctx.state), ctx.options);
    if (op.index != null) checkIndex(op.index);
    const position = op.index == null ? choices.length : Math.min(op.index, choices.length);
    target.choices = insertedAt(choices, position, choice);
    return `Added a choice to '${titleText(field)}'`;
};

export const removeChoice: Handler<RemoveChoiceOp> = (ctx, op) => {
    const { field, choices, target } = choiceField(ctx, op.fieldId, true);
    const position = choicePosition(field, choices, op.choiceId);
    target.choices = choices.filter((_, i) => i !== position);
    return `Removed a choice of '${titleText(field)}'`;
};

export const moveChoice: Handler<MoveChoiceOp> = (ctx, op) => {
    const { field, choices, target } = choiceField(ctx, op.fieldId, false);
    const from = choicePosition(field, choices, op.choiceId);
    const index = checkIndex(op.index);
    const rest = choices.filter((_, i) => i !== from);
    const position = Math.min(index, rest.length);
    target.choices = insertedAt(rest, position, choices[from]);
    return `Moved a choice of '${titleText(field)}' to position ${position + 1}`;
};

/** Fields in an editor payload, nested ones included. */
function payloadCount(raw: any): number {
    let total = 0;
    const pending = [raw];
    while (pending.length) {
        const item = pending.pop();
        if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
        total += 1;
        if (Array.isArray(item.properties?.fields)) pending.push(...item.properties.fields);
    }
    return total;
}

/** Pages and fields an editor op adds (backend `_editor_growth`), known before it runs. */
export function editorGrowth(doc: FormDoc, op: InsertFieldOp | InsertPageOp | ReplaceFieldOp): [number, number] {
    if (op.op === 'insert_field') return [0, payloadCount(op.field)];
    if (op.op === 'insert_page') return [1, Math.max(0, payloadCount(op.page) - 1)];
    try {
        const old = locateField(doc, op.field?.id).field;
        return [0, Math.max(0, payloadCount(op.field) - countFields([old]))];
    } catch {
        return [0, 0];
    }
}
