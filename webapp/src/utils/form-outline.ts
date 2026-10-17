import { JSONContent } from '@tiptap/react';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { LogicCondition, PageJump } from '@app/models/types/form-builder-shared';
import { ANSWER_PIPE_NODE } from '@app/utils/answer-piping';
import { isJumpTargetValid, slideHasLogic } from '@app/utils/conditional-logic';
import { Ending, isJumpEndingMissing } from '@app/utils/endings';
import { getPublishProblems, questionText } from '@app/utils/publish-checks';

/**
 * The builder outline: reordering pages and questions, and what the outline
 * says about each page.
 *
 * Logic refers to questions by id (conditions, answer pipes, date rules) and
 * to pages by id (jump targets), so a move never leaves a dangling id. What a
 * move can break is ORDER: a show/hide rule, a pipe or a date rule may only
 * use an answer given before its question, and a page jump only answers from
 * its own page or earlier ones (the same scoping the logic editors offer).
 * After a move, `pruneOutOfOrderReferences` removes the references the move
 * turned around, and only those; the move is one undo step, so Undo brings
 * them back with the old order.
 */

/** Renumber `index` to match array order. */
const renumber = (items: StandardFormFieldDto[] | undefined) => items?.forEach((item, index) => (item.index = index));

/** Move page `from` to position `to` (in place). False when nothing moved. */
export function movePageInSlides(slides: StandardFormFieldDto[], from: number, to: number): boolean {
    if (from === to || from < 0 || to < 0 || from >= slides.length || to >= slides.length) return false;
    const [page] = slides.splice(from, 1);
    slides.splice(to, 0, page);
    renumber(slides);
    return true;
}

export interface FieldLocation {
    pageIndex: number;
    fieldIndex: number;
}

/** Where a page-level question is. Questions inside a group are not page-level. */
export function locateField(slides: StandardFormFieldDto[], fieldId: string): FieldLocation | null {
    for (let pageIndex = 0; pageIndex < slides.length; pageIndex++) {
        const fieldIndex = slides[pageIndex]?.properties?.fields?.findIndex((field) => field.id === fieldId) ?? -1;
        if (fieldIndex >= 0) return { pageIndex, fieldIndex };
    }
    return null;
}

/**
 * Move a page-level question to page `toPageIndex` at position `toIndex`
 * (counted in the target page after the question left its old place; clamped
 * to the page). In place. Returns where it was, or null when nothing moved.
 */
export function moveFieldInSlides(slides: StandardFormFieldDto[], fieldId: string, toPageIndex: number, toIndex: number): FieldLocation | null {
    const from = locateField(slides, fieldId);
    const target = slides[toPageIndex];
    if (!from || !target) return null;
    const source = slides[from.pageIndex];
    const [field] = source.properties!.fields!.splice(from.fieldIndex, 1);
    target.properties = { ...(target.properties || {}), fields: target.properties?.fields ?? [] };
    const fields = target.properties.fields!;
    const at = Math.max(0, Math.min(toIndex, fields.length));
    if (from.pageIndex === toPageIndex && at === from.fieldIndex) {
        fields.splice(at, 0, field);
        return null;
    }
    fields.splice(at, 0, field);
    renumber(source.properties!.fields);
    if (target !== source) renumber(fields);
    return from;
}

/** Ids of a page-level question and of the questions inside it (repeating group). */
export function fieldAndChildIds(field: StandardFormFieldDto | undefined): string[] {
    if (!field) return [];
    return [field.id, ...(field.type === FieldTypes.GROUP ? (field.properties?.fields ?? []).map((child) => child.id) : [])];
}

interface Position {
    page: number;
    index: number;
    /** The repeating group a question sits in; its position is the group's. */
    groupId?: string;
}

function positions(slides: StandardFormFieldDto[]): Map<string, Position> {
    const map = new Map<string, Position>();
    slides.forEach((slide, page) =>
        slide?.properties?.fields?.forEach((field, index) => {
            map.set(field.id, { page, index });
            if (field?.type === FieldTypes.GROUP) field.properties?.fields?.forEach((child) => map.set(child.id, { page, index, groupId: field.id }));
        })
    );
    return map;
}

const before = (source: Position, owner: Position) => source.page < owner.page || (source.page === owner.page && source.index < owner.index);

/**
 * Remove the logic references a move turned around: show/hide conditions,
 * answer pipes and date rules that now use a later answer, and page-jump
 * conditions that now use an answer from a later page. Only references that
 * involve `movedFieldIds` (as user or source) or a jump on a page in
 * `movedPageIds` are looked at, so a reorder never touches unrelated rules.
 * References to questions that no longer exist are left to the orphan
 * sweepers. Mutates in place; returns how many references it removed.
 */
export function pruneOutOfOrderReferences(slides: StandardFormFieldDto[], movedFieldIds: Set<string>, movedPageIds: Set<string> = new Set()): number {
    const pos = positions(slides);
    let removed = 0;

    // May `owner` use `sourceId`'s answer? Questions of one repeating group may use each other.
    const usable = (ownerId: string, sourceId: string | undefined): boolean => {
        if (!sourceId) return true;
        const owner = pos.get(ownerId);
        const source = pos.get(sourceId);
        if (!owner || !source) return true;
        if (!movedFieldIds.has(ownerId) && !movedFieldIds.has(sourceId)) return true;
        if (source.groupId && source.groupId === owner.groupId) return true;
        return before(source, owner);
    };

    const pruneConditions = (conditions: LogicCondition[] | undefined, keep: (c: LogicCondition) => boolean): LogicCondition[] => {
        const kept = (conditions ?? []).filter((condition) => !condition || keep(condition));
        removed += (conditions?.length ?? 0) - kept.length;
        return kept;
    };

    const pipeSource = (node: JSONContent): string | undefined => {
        const attrs = node.attrs ?? {};
        if (attrs.kind === 'hidden') return undefined;
        if (attrs.kind === 'group') return String(attrs.pipeKey ?? '').split(':')[0];
        return attrs.pipeKey;
    };
    const prunePipes = (ownerId: string, node: JSONContent | undefined): void => {
        if (!node?.content?.length) return;
        const kept = node.content.filter((child) => child?.type !== ANSWER_PIPE_NODE || usable(ownerId, pipeSource(child)));
        removed += node.content.length - kept.length;
        node.content = kept;
        node.content.forEach((child) => prunePipes(ownerId, child));
    };

    const pruneField = (field: StandardFormFieldDto) => {
        const props = field?.properties;
        if (props?.logic) {
            const conditions = pruneConditions(props.logic.conditions, (c) => usable(field.id, c.fieldId));
            if (conditions.length) props.logic = { ...props.logic, conditions };
            else delete props.logic;
        }
        if (props?.dateRules) {
            const rules = props.dateRules.filter((rule) => rule.target !== 'field' || usable(field.id, rule.fieldId));
            removed += props.dateRules.length - rules.length;
            if (rules.length) props.dateRules = rules;
            else delete props.dateRules;
        }
        if (field?.title && typeof field.title !== 'string') prunePipes(field.id, field.title as JSONContent);
    };

    slides.forEach((slide, page) => {
        const props = slide?.properties;
        if (!props) return;
        props.fields?.forEach((field) => {
            pruneField(field);
            if (field?.type === FieldTypes.GROUP) field.properties?.fields?.forEach(pruneField);
        });
        if (Array.isArray(props.jumps)) {
            const pageMoved = movedPageIds.has(slide.id);
            const jumps = (props.jumps as PageJump[])
                .map((jump) => {
                    const conditions = pruneConditions(jump.conditions, (c) => {
                        const source = pos.get(c.fieldId);
                        if (!source || (!pageMoved && !movedFieldIds.has(c.fieldId))) return true;
                        return source.page <= page;
                    });
                    return { ...jump, conditions };
                })
                // A jump left without conditions would fire for everyone.
                .filter((jump, i) => jump.conditions.length > 0 || !(props.jumps as PageJump[])[i]?.conditions?.length);
            if (jumps.length) props.jumps = jumps;
            else delete props.jumps;
        }
    });
    return removed;
}

/** What the outline shows about a page. */
export interface PageStatus {
    hasLogic: boolean;
    brokenJumps: number;
    empty: boolean;
    /** Questions that ask for personal details without a "why we ask this" line. */
    missingWhyWeAsk: number;
    internal: number;
}

/** Same rules as the Flow view's page badges and the publish checks. */
export function pageStatus(slide: StandardFormFieldDto, slideIds: Set<string>, endings?: Ending[]): PageStatus {
    const fields = slide?.properties?.fields ?? [];
    const jumps = (slide?.properties?.jumps as PageJump[] | undefined) ?? [];
    return {
        hasLogic: slideHasLogic(slide),
        brokenJumps: jumps.filter((jump) => jump?.conditions?.length && (!isJumpTargetValid(jump.target, slideIds) || (endings !== undefined && isJumpEndingMissing(jump, endings)))).length,
        empty: fields.length === 0,
        missingWhyWeAsk: getPublishProblems([slide]).filter((problem) => problem.code === 'missing_why_we_ask').length,
        internal: fields.filter((field) => field?.internal).length
    };
}

/** A page's name in the outline: its own section title, else "Page n". */
export function outlinePageName(slide: StandardFormFieldDto | undefined, index: number): string {
    return slide?.properties?.sectionTitle?.trim() || `Page ${index + 1}`;
}

/** Does a question's plain-text title contain `query` (case-insensitive)? */
export function questionMatches(field: StandardFormFieldDto, query: string): boolean {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return questionText(field).toLowerCase().includes(q);
}

/* ---------------- drag and drop over the flattened outline ---------------- */

export const PAGE_KEY = 'page:';
export const QUESTION_KEY = 'question:';
export const pageKey = (id: string) => `${PAGE_KEY}${id}`;
export const questionKey = (id: string) => `${QUESTION_KEY}${id}`;
export const keyId = (key: string) => key.slice(key.indexOf(':') + 1);
export const isPageKey = (key: string) => key.startsWith(PAGE_KEY);

/** Move one entry of a list (a copy). */
export function arrayMoveCopy<T>(list: T[], from: number, to: number): T[] {
    const next = list.slice();
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    return next;
}

export type OutlineDrop = { kind: 'page'; from: number; to: number } | { kind: 'question'; fieldId: string; toPageId: string; afterFieldId: string | null };

/**
 * The outline is one flat sortable list: each page's key followed by the
 * keys of its shown questions. Moving `activeKey` onto `overKey` is a plain
 * array move of that list; what it means is read back from the result:
 *  - a page: the new order of the page keys;
 *  - a question: the page whose key now precedes it, after the question
 *    shown just above it on that page (none: the top of the page).
 * Questions of a collapsed or filtered page are not in the list; anchoring on
 * the question shown above keeps them where they are.
 */
export function resolveOutlineDrop(flatKeys: string[], activeKey: string, overKey: string): OutlineDrop | null {
    const from = flatKeys.indexOf(activeKey);
    const to = flatKeys.indexOf(overKey);
    if (from < 0 || to < 0 || from === to) return null;
    const moved = arrayMoveCopy(flatKeys, from, to);
    if (isPageKey(activeKey)) {
        const before = flatKeys.filter(isPageKey);
        const after = moved.filter(isPageKey);
        const pageFrom = before.indexOf(activeKey);
        const pageTo = after.indexOf(activeKey);
        return pageFrom === pageTo ? null : { kind: 'page', from: pageFrom, to: pageTo };
    }
    const at = moved.indexOf(activeKey);
    let afterFieldId: string | null = null;
    let toPageKey: string | undefined;
    for (let i = at - 1; i >= 0; i--) {
        if (isPageKey(moved[i])) {
            toPageKey = moved[i];
            break;
        }
        if (afterFieldId === null) afterFieldId = keyId(moved[i]);
    }
    // Dropped above the first page: the top of the first page.
    if (!toPageKey) {
        toPageKey = moved.find(isPageKey);
        afterFieldId = null;
    }
    if (!toPageKey) return null;
    return { kind: 'question', fieldId: keyId(activeKey), toPageId: keyId(toPageKey), afterFieldId };
}

/**
 * Where a question dropped on page `toPageId` after `afterFieldId` goes, in
 * the terms `moveFieldInSlides` takes (position counted without the question).
 */
export function questionDropTarget(slides: StandardFormFieldDto[], fieldId: string, toPageId: string, afterFieldId: string | null): { toPageIndex: number; toIndex: number } | null {
    const toPageIndex = slides.findIndex((slide) => slide.id === toPageId);
    if (toPageIndex < 0) return null;
    if (!afterFieldId) return { toPageIndex, toIndex: 0 };
    const others = (slides[toPageIndex].properties?.fields ?? []).filter((field) => field.id !== fieldId);
    return { toPageIndex, toIndex: others.findIndex((field) => field.id === afterFieldId) + 1 };
}
