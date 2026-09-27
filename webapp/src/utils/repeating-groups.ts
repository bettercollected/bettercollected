import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { RepeatSettings } from '@app/models/types/form-builder-shared';
import { PipeContext, resolvePipesInText } from '@app/utils/answer-piping';
import { getGroupAnswerItems, getHiddenFieldIds } from '@app/utils/conditional-logic';

/**
 * Repeating groups — a set of questions respondents fill several times (one
 * block per applicant, family member, employer, item).
 *
 * Model: a `group` field with `properties.repeat` (see RepeatSettings) whose
 * child questions live in `properties.fields`.
 *
 * Answer: stored under the group id, one answers map per item, each keyed by
 * child field id and shaped like a top-level answer:
 *     answers[groupId] = { type: 'group', items: [{ [childId]: answer }, ...] }
 * Other answers are untouched, so existing responses keep working.
 *
 * Item scope: while an item renders, its answers are layered over the form's
 * (`itemScopeAnswers`), so the existing field components, visibility rules and
 * answer pipes work unchanged — and a reference to a sibling question means
 * "this item's answer". Inside the scope, each child renders under a scoped id
 * (`<childId>::<itemIndex>`) so DOM ids and validation messages stay unique.
 *
 * The backend enforces the same limits (backend/app/services/repeating_groups.py).
 */

/** Items per group, whatever the creator asks for (mirrors the backend). */
export const REPEAT_MAX_ITEMS_LIMIT = 50;
/** Up to this many items a group exports as columns per item by default. */
export const REPEAT_COLUMNS_EXPORT_MAX = 5;

/** Child question types allowed inside a repeating group (v1, mirrors the backend). */
export const REPEAT_CHILD_FIELD_TYPES: string[] = [
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
    FieldTypes.TEXT
];

export const GROUP_ANSWER_TYPE = 'group';

export interface ResolvedRepeatSettings {
    minItems: number;
    maxItems: number;
    itemLabel: string;
    itemTitle?: string;
    exportLayout: 'columns' | 'rows';
}

export function isRepeatingGroup(field: StandardFormFieldDto | undefined | null): boolean {
    return !!field && field.type === FieldTypes.GROUP && !!field.properties?.repeat;
}

const clampInt = (value: any, min: number, max: number, fallback: number) => {
    const n = Math.floor(Number(value));
    return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback;
};

/** Repeat settings with defaults applied and limits clamped. */
export function getRepeatSettings(field: StandardFormFieldDto | undefined): ResolvedRepeatSettings {
    const repeat: RepeatSettings = field?.properties?.repeat ?? {};
    const maxItems = clampInt(repeat.maxItems, 1, REPEAT_MAX_ITEMS_LIMIT, 3);
    const minItems = Math.min(clampInt(repeat.minItems, 0, REPEAT_MAX_ITEMS_LIMIT, 1), maxItems);
    const exportLayout = repeat.exportLayout === 'columns' || repeat.exportLayout === 'rows' ? repeat.exportLayout : maxItems <= REPEAT_COLUMNS_EXPORT_MAX ? 'columns' : 'rows';
    return { minItems, maxItems, itemLabel: repeat.itemLabel?.trim() || 'Item', itemTitle: repeat.itemTitle, exportLayout };
}

export function getGroupChildren(field: StandardFormFieldDto | undefined): StandardFormFieldDto[] {
    return field?.properties?.fields ?? [];
}

export { getGroupAnswerItems };

export function getGroupItems(answers: Record<string, any> | undefined, groupId: string): Array<Record<string, any>> {
    return getGroupAnswerItems(answers?.[groupId]);
}

/** How many item blocks the respondent sees: at least the minimum, at most the maximum. */
export function getDisplayedItemCount(field: StandardFormFieldDto, answers: Record<string, any> | undefined): number {
    const { minItems, maxItems } = getRepeatSettings(field);
    return Math.min(maxItems, Math.max(minItems, getGroupItems(answers, field.id).length));
}

const SCOPE_SEPARATOR = '::';

/** Id a child question renders under inside item `index` (unique in the DOM and in validation). */
export function scopedFieldId(childId: string, index: number): string {
    return `${childId}${SCOPE_SEPARATOR}${index}`;
}

export function parseScopedFieldId(id: string): { childId: string; index: number } | null {
    const at = id.lastIndexOf(SCOPE_SEPARATOR);
    if (at <= 0) return null;
    const index = Number(id.slice(at + SCOPE_SEPARATOR.length));
    return Number.isInteger(index) && index >= 0 ? { childId: id.slice(0, at), index } : null;
}

export interface ItemScope {
    groupId: string;
    index: number;
    childIds: string[];
}

/**
 * Answers as seen from inside one item: the form's answers, with this item's
 * answers layered on top under both the child ids (for logic and pipes) and
 * the scoped ids (for the field components themselves).
 */
export function itemScopeAnswers(answers: Record<string, any> | undefined, scope: ItemScope): Record<string, any> {
    const item = getGroupItems(answers, scope.groupId)[scope.index] ?? {};
    const view: Record<string, any> = { ...(answers || {}) };
    scope.childIds.forEach((childId) => {
        if (item[childId] !== undefined) {
            view[childId] = item[childId];
            view[scopedFieldId(childId, scope.index)] = item[childId];
        } else {
            delete view[childId];
        }
    });
    return view;
}

/**
 * Write back what a field component produced inside an item: the scoped keys
 * of `scopedAnswers` become the item's answers. Items before `index` that do
 * not exist yet are created empty. Returns new answers; the input is not mutated.
 */
export function writeItemAnswers(answers: Record<string, any> | undefined, scope: ItemScope, scopedAnswers: Record<string, any>): Record<string, any> {
    const items = getGroupItems(answers, scope.groupId).map((item) => ({ ...item }));
    while (items.length <= scope.index) items.push({});
    const item: Record<string, any> = {};
    scope.childIds.forEach((childId) => {
        const value = scopedAnswers?.[scopedFieldId(childId, scope.index)];
        if (value !== undefined && value !== null) item[childId] = value;
    });
    items[scope.index] = item;
    return { ...(answers || {}), [scope.groupId]: { ...(answers?.[scope.groupId] || {}), type: GROUP_ANSWER_TYPE, items } };
}

/** Pad a group's answer to the items the respondent sees (at least the minimum). */
export function ensureGroupItems(answers: Record<string, any> | undefined, field: StandardFormFieldDto): Record<string, any> {
    const count = getDisplayedItemCount(field, answers);
    const items = getGroupItems(answers, field.id).slice(0, count);
    while (items.length < count) items.push({});
    return { ...(answers || {}), [field.id]: { ...(answers?.[field.id] || {}), type: GROUP_ANSWER_TYPE, items } };
}

export function canAddItem(field: StandardFormFieldDto, answers: Record<string, any> | undefined): boolean {
    return getDisplayedItemCount(field, answers) < getRepeatSettings(field).maxItems;
}

export function canRemoveItem(field: StandardFormFieldDto, answers: Record<string, any> | undefined): boolean {
    return getDisplayedItemCount(field, answers) > getRepeatSettings(field).minItems;
}

export function addGroupItem(answers: Record<string, any> | undefined, field: StandardFormFieldDto): Record<string, any> {
    const padded = ensureGroupItems(answers, field);
    if (!canAddItem(field, padded)) return padded;
    const items = [...getGroupItems(padded, field.id), {}];
    return { ...padded, [field.id]: { ...padded[field.id], items } };
}

export function removeGroupItem(answers: Record<string, any> | undefined, field: StandardFormFieldDto, index: number): Record<string, any> {
    const padded = ensureGroupItems(answers, field);
    if (!canRemoveItem(field, padded)) return padded;
    const items = getGroupItems(padded, field.id).filter((_, i) => i !== index);
    return { ...padded, [field.id]: { ...padded[field.id], items } };
}

/** Every repeating group of a form (groups live on pages). */
export function getRepeatingGroups(slides: Array<StandardFormFieldDto> | undefined): StandardFormFieldDto[] {
    const groups: StandardFormFieldDto[] = [];
    (slides ?? []).forEach((slide) => slide?.properties?.fields?.forEach((field) => isRepeatingGroup(field) && groups.push(field)));
    return groups;
}

/**
 * Shape group answers for submission: a group the respondent saw is padded to
 * its minimum (an untouched optional item is still an item) and cut to its
 * maximum. Groups never shown (hidden by logic, skipped pages) stay absent.
 */
export function normalizeGroupAnswersForSubmit(slides: Array<StandardFormFieldDto> | undefined, answers: Record<string, any>): Record<string, any> {
    let next = { ...(answers || {}) };
    getRepeatingGroups(slides).forEach((group) => {
        if (next[group.id] === undefined) return;
        next = ensureGroupItems(next, group);
    });
    return next;
}

/** Child questions hidden right now in item `index` (item-scoped visibility rules). */
export function getItemHiddenChildIds(field: StandardFormFieldDto, answers: Record<string, any> | undefined, index: number): Set<string> {
    const children = getGroupChildren(field);
    return getHiddenFieldIds(children, itemScopeAnswers(answers, { groupId: field.id, index, childIds: children.map((c) => c.id) }));
}

export type GroupInvalidation = 'REQUIRED' | 'MIN_ITEMS' | 'MAX_ITEMS';

/**
 * Validate one group: item count within limits (keyed by the group id) and
 * required questions per visible item (keyed by the scoped child id).
 */
export function validateGroupAnswer(field: StandardFormFieldDto, answers: Record<string, any> | undefined): Record<string, GroupInvalidation[]> {
    const invalid: Record<string, GroupInvalidation[]> = {};
    const { minItems, maxItems } = getRepeatSettings(field);
    const count = getDisplayedItemCount(field, answers);
    const stored = getGroupItems(answers, field.id).length;
    if (stored > maxItems) invalid[field.id] = ['MAX_ITEMS'];
    else if (count < minItems) invalid[field.id] = ['MIN_ITEMS'];
    const items = getGroupItems(answers, field.id);
    for (let index = 0; index < count; index++) {
        const item = items[index] ?? {};
        const hidden = getItemHiddenChildIds(field, answers, index);
        getGroupChildren(field).forEach((child) => {
            if (child?.validations?.required && !hidden.has(child.id) && !item[child.id]) invalid[scopedFieldId(child.id, index)] = ['REQUIRED'];
        });
    }
    return invalid;
}

/** Validate the repeating groups among a page's visible fields. */
export function validateGroupsInSlide(fields: Array<StandardFormFieldDto> | undefined, answers: Record<string, any> | undefined): Record<string, GroupInvalidation[]> {
    return (fields ?? []).filter(isRepeatingGroup).reduce((acc, group) => ({ ...acc, ...validateGroupAnswer(group, answers) }), {} as Record<string, GroupInvalidation[]>);
}

/**
 * Header of item `index`: "<label> <n>", plus the resolved item title
 * template when it has content ("Applicant 2: Sita Sharma"). The template's
 * sibling pipes resolve against this item.
 */
export function getItemHeader(field: StandardFormFieldDto, index: number, context: PipeContext): string {
    const { itemLabel, itemTitle } = getRepeatSettings(field);
    const base = `${itemLabel} ${index + 1}`;
    if (!itemTitle?.trim()) return base;
    const scope = { groupId: field.id, index, childIds: getGroupChildren(field).map((c) => c.id) };
    // The group's own questions are always resolvable, even when the caller's
    // slides are stale or partial (e.g. a preview of a single page).
    const slides = [...(context.slides ?? []), { id: `${field.id}-scope`, index: -1, type: FieldTypes.SLIDE, properties: { fields: [field] } } as StandardFormFieldDto];
    const resolved = resolvePipesInText(itemTitle, { ...context, slides, answers: itemScopeAnswers(context.answers, scope) })?.trim();
    return resolved ? `${base}: ${resolved}` : base;
}
