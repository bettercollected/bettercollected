/** Page ops: add, remove, move, duplicate, jumps, section titles, numbering. */
import { FieldTypes } from '@app/models/dtos/form';

import { JUMP_TARGET_SUBMIT, MAX_NEW_PAGE_FIELDS, OpError, SECTION_TITLE_MAX_LENGTH, childrenOf, clone, collapseWhitespace, findPage, isRepeatingGroup, locateField, pagesOf, pyLen, subtreeIds, titleText } from '../model';
import type { AddPageOp, DuplicatePageOp, FormField, MovePageOp, RemovePageOp, SetPageJumpsOp, SetQuestionNumberingOp, SetSectionTitleOp } from '../types';
import { type Handler, droppedReferencesNote, droppedRulesNote, ensureProperties, insertedAt, removedAt, setKey } from './context';
import { buildField, validatedConditions } from './fields';

export const NEW_PAGE_LAYOUT = 'SINGLE_COLUMN_NO_BACKGROUND';

/** Position in `doc.fields` for a page placed at `index` among the question pages (append when null or past the end). */
export function pageInsertPosition(top: FormField[], pages: FormField[], index: number | null | undefined): number {
    if (index == null || index >= pages.length) return top.length;
    return top.indexOf(pages[Math.max(0, index)]);
}

export const addPage: Handler<AddPageOp> = (ctx, op) => {
    if ((op.fields?.length ?? 0) > MAX_NEW_PAGE_FIELDS) throw new OpError(`List should have at most ${MAX_NEW_PAGE_FIELDS} items after validation, not ${op.fields!.length}`);
    if (ctx.draft.fields == null) ctx.draft.fields = [];
    const fields = (op.fields ?? []).map((spec, i) => buildField(spec, i, ctx.newId));
    const page: FormField = { id: ctx.newId(), index: 0, type: FieldTypes.SLIDE, properties: { fields, layout: NEW_PAGE_LAYOUT as any }, validations: {} };
    const top = ctx.state.fields ?? [];
    ctx.draft.fields = insertedAt(top, pageInsertPosition(top, pagesOf(ctx.state), op.index), page) as any;
    ctx.noteCreated(
        page.id,
        fields.map((f) => f.id)
    );
    return `Added a page with ${fields.length} field(s)`;
};

export const removePage: Handler<RemovePageOp> = (ctx, op) => {
    const { page, pos } = findPage(ctx.state, op.pageId);
    ctx.draft.fields = removedAt(ctx.state.fields ?? [], pos) as any;
    return `Removed a page (${childrenOf(page).length} field(s) with it)${droppedRulesNote()}${droppedReferencesNote(ctx, subtreeIds(page))}`;
};

export const movePage: Handler<MovePageOp> = (ctx, op) => {
    const { page, pos } = findPage(ctx.state, op.pageId);
    if (op.index < 0) throw new OpError("A page's new position (index) must be 0 or more.");
    const pages = pagesOf(ctx.state);
    const old = pages.indexOf(page);
    const rest = pages.filter((p) => p !== page);
    const target = Math.min(op.index, rest.length);
    const top = (ctx.state.fields ?? []).filter((_, i) => i !== pos);
    ctx.draft.fields = insertedAt(top, target >= rest.length ? top.length : top.indexOf(rest[target]), page) as any;
    if (target === old) return `Page ${old + 1} stays at position ${old + 1}`;
    return `Moved page ${old + 1} to position ${target + 1}`;
};

export const setPageJumps: Handler<SetPageJumpsOp> = (ctx, op) => {
    const { pos } = findPage(ctx.state, op.pageId);
    const properties = ensureProperties(ctx.draft.fields![pos], false);
    if (op.jumps == null) {
        setKey(properties, 'jumps', undefined);
        return `Cleared page jumps on page '${op.pageId}'`;
    }
    const jumps = op.jumps.map((spec) => {
        if (spec.target !== JUMP_TARGET_SUBMIT) {
            const target = findPage(ctx.state, spec.target);
            if (target.page.id === op.pageId) throw new OpError('A page cannot jump to itself.');
        }
        if (!spec.conditions?.length) throw new OpError('List should have at least 1 item after validation, not 0');
        return { operator: spec.operator ?? 'AND', conditions: validatedConditions(ctx.state, spec.conditions), target: spec.target };
    });
    properties.jumps = jumps as any;
    return `Set ${jumps.length} jump rule(s) on page '${op.pageId}'`;
};

export const duplicatePage: Handler<DuplicatePageOp> = (ctx, op) => {
    const { page: original, pos } = findPage(ctx.state, op.pageId);
    const page = clone(original);
    page.id = ctx.newId();
    const idMap = new Map<string, string>();
    const pageFields = childrenOf(page);
    const all = [...pageFields, ...pageFields.filter(isRepeatingGroup).flatMap(childrenOf)];
    for (const field of all) {
        const id = ctx.newId();
        idMap.set(field.id, id);
        field.id = id;
        for (const choice of field.properties?.choices ?? []) choice.id = ctx.newId();
    }
    // Remap in-page references onto the copies; references outside the page stay.
    for (const field of all) {
        for (const condition of field.properties?.logic?.conditions ?? []) {
            if (idMap.has(condition.fieldId)) condition.fieldId = idMap.get(condition.fieldId)!;
            if (condition.childFieldId && idMap.has(condition.childFieldId)) condition.childFieldId = idMap.get(condition.childFieldId)!;
        }
        for (const rule of field.properties?.dateRules ?? []) if (rule.fieldId && idMap.has(rule.fieldId)) rule.fieldId = idMap.get(rule.fieldId)!;
        const repeat = field.properties?.repeat;
        if (repeat?.itemTitle) for (const [oldId, newId] of idMap) repeat.itemTitle = repeat.itemTitle.split(oldId).join(newId);
    }
    // Copied jumps would re-branch from the copy in surprising ways: dropped.
    if (page.properties) {
        delete page.properties.jumps;
        delete page.properties.position;
    }
    const top = ctx.state.fields ?? [];
    const at = Math.max(0, Math.min(op.index ?? pos + 1, top.length));
    ctx.draft.fields = insertedAt(top, at, page) as any;
    ctx.noteCreated(page.id);
    return `Duplicated page '${op.pageId}' (${pageFields.length} fields) as '${page.id}'`;
};

const WELCOME_PAGE_IDS = new Set(['welcome', 'welcome_page', 'welcomepage', 'start', 'intro']);
const ENDING_PAGE_IDS = new Set(['ending', 'end', 'thankyou', 'thank_you', 'thankyou_page', 'thank_you_page', 'thankyoupage']);
const noSectionTitle = (page: string, instead: string) => `Only question pages have a section title; the ${page} has none. Change the ${instead} instead.`;

function sectionPage(ctx: Parameters<Handler<SetSectionTitleOp>>[0], op: SetSectionTitleOp): { pos: number; number: number } {
    const pages = pagesOf(ctx.state);
    const top = ctx.state.fields ?? [];
    if ((op.pageId == null) === (op.pageIndex == null)) throw new OpError('set_section_title needs either a pageId or a pageIndex.');
    if (op.pageIndex != null) {
        if (!(op.pageIndex >= 0 && op.pageIndex < pages.length)) throw new OpError(`There is no page with index ${op.pageIndex}: the form has ${pages.length} question page(s), indexed from 0.`);
        return { pos: top.indexOf(pages[op.pageIndex]), number: op.pageIndex + 1 };
    }
    const key = op.pageId!.trim().toLowerCase();
    if (WELCOME_PAGE_IDS.has(key)) throw new OpError(noSectionTitle('welcome page', 'form title'));
    if (ENDING_PAGE_IDS.has(key)) throw new OpError(noSectionTitle('ending', "ending's heading"));
    const number = pages.findIndex((p) => p.id === op.pageId);
    if (number >= 0) return { pos: top.indexOf(pages[number]), number: number + 1 };
    let field: FormField;
    try {
        field = locateField(ctx.state, op.pageId!).field;
    } catch {
        throw new OpError(`Page '${op.pageId}' was not found — it may have been removed.`);
    }
    throw new OpError(`'${titleText(field)}' is a question, not a page: use the id of the page it is on.`);
}

export const setSectionTitle: Handler<SetSectionTitleOp> = (ctx, op) => {
    if (!('title' in op)) throw new OpError('set_section_title needs a "title" (null or "" clears it).');
    const { pos, number } = sectionPage(ctx, op);
    // Plain text on one line: runs of whitespace (newlines too) become a space.
    const title = collapseWhitespace(op.title ?? '');
    if (pyLen(title) > SECTION_TITLE_MAX_LENGTH) {
        throw new OpError(`A section title can be at most ${SECTION_TITLE_MAX_LENGTH} characters (this one has ${pyLen(title)}). Keep it short and plain.`);
    }
    setKey(ensureProperties(ctx.draft.fields![pos]), 'sectionTitle', title || undefined);
    if (!title) return `Cleared the section title of page ${number} (it shows its opening heading or first question again)`;
    return `Section title of page ${number}: '${title}'`;
};

export const setQuestionNumbering: Handler<SetQuestionNumberingOp> = (ctx, op) => {
    const top = ctx.state.fields ?? [];
    let targets: number[];
    let where: string;
    if (op.pageId != null) {
        const { pos, number } = findPage(ctx.state, op.pageId);
        targets = [pos];
        where = `page ${number}`;
    } else {
        const pages = pagesOf(ctx.state);
        if (!pages.length) throw new OpError('The form has no question pages to number.');
        targets = pages.map((p) => top.indexOf(p));
        where = 'every page';
    }
    for (const pos of targets) {
        const properties = ensureProperties(ctx.draft.fields![pos]);
        if (properties.showQuestionNumbers !== op.show) properties.showQuestionNumbers = op.show;
    }
    return `Turned question numbers ${op.show ? 'on' : 'off'} for ${where}`;
};
