/** Question ops: add, update, remove, move, answer rules, visibility logic. */
import type { Draft } from 'immer';

import { FieldTypes } from '@app/models/dtos/form';

import { checkedDateRules, dateRuleProblems, dateRuleSources } from '../date-rules';
import {
    ADDABLE_FIELD_TYPES,
    CHOICE_FIELD_TYPES,
    INTERNAL_IN_GROUP_MESSAGE,
    LABEL_MAX_LENGTH,
    OpError,
    PATTERN_MAX_LENGTH,
    RATING_FIELD_TYPES,
    REPEAT_MAX_ITEMS_LIMIT,
    WHY_WE_ASK_MAX_LENGTH,
    checkChildType,
    childrenOf,
    ensureCanBeInternal,
    findGroup,
    findPage,
    isRepeatingGroup,
    locateField,
    pagesOf,
    pyG,
    pyLen,
    pyStr,
    sortedList,
    titleText
} from '../model';
import type { AddFieldOp, AddGroupOp, FieldPatch, FormDoc, FormField, LogicConditionSpec, MoveFieldOp, NewFieldSpec, RemoveFieldOp, SetFieldLogicOp, SetFieldValidationOp, UpdateFieldOp } from '../types';
import { type Handler, draftField, draftOwner, droppedReferencesNote, droppedRulesNote, ensureFields, ensureProperties, insertedAt, removedAt, setFields, setKey } from './context';
import { checkTitle } from './editor';

// ---------------------------------------------------------------------------
// Parse-time checks the backend's models make (pydantic messages)
// ---------------------------------------------------------------------------

export function checkColSpan(value: number | null | undefined): void {
    if (value == null) return;
    if (value < 1) throw new OpError('Input should be greater than or equal to 1');
    if (value > 12) throw new OpError('Input should be less than or equal to 12');
}

export function checkMaxLength(value: string | null | undefined, max: number): void {
    if (typeof value === 'string' && pyLen(value) > max) throw new OpError(`String should have at most ${max} characters`);
}

function checkSpec(spec: NewFieldSpec): void {
    checkColSpan(spec.colSpan);
    checkMaxLength(spec.label, LABEL_MAX_LENGTH);
    checkMaxLength(spec.whyWeAsk, WHY_WE_ASK_MAX_LENGTH);
}

/** Problems of repeat settings, as pydantic reports them (RepeatSettings). */
export function repeatProblems(repeat: Record<string, any>): string | null {
    const errors: string[] = [];
    const bound = (value: any, low: number, high: number) => {
        if (value == null) return;
        if (value < low) errors.push(`Input should be greater than or equal to ${low}`);
        else if (value > high) errors.push(`Input should be less than or equal to ${high}`);
    };
    bound(repeat.minItems, 0, REPEAT_MAX_ITEMS_LIMIT);
    bound(repeat.maxItems, 1, REPEAT_MAX_ITEMS_LIMIT);
    if (typeof repeat.itemLabel === 'string' && pyLen(repeat.itemLabel) > 80) errors.push('String should have at most 80 characters');
    if (typeof repeat.itemTitle === 'string' && pyLen(repeat.itemTitle) > 300) errors.push('String should have at most 300 characters');
    if (repeat.exportLayout != null && repeat.exportLayout !== 'columns' && repeat.exportLayout !== 'rows') errors.push("Input should be 'columns' or 'rows'");
    if (errors.length) return errors.join('; ');
    if (repeat.minItems != null && repeat.maxItems != null && repeat.minItems > repeat.maxItems) return "A repeating group's minimum number of items cannot exceed its maximum.";
    return null;
}

const REPEAT_KEYS = ['minItems', 'maxItems', 'itemLabel', 'itemTitle', 'exportLayout'] as const;
const REPEAT_KEY_LABELS: Record<(typeof REPEAT_KEYS)[number], string> = { minItems: 'min items', maxItems: 'max items', itemLabel: 'item label', itemTitle: 'item title', exportLayout: 'export layout' };

function compactRepeat(repeat: Record<string, any>): Record<string, any> {
    const out: Record<string, any> = {};
    for (const key of REPEAT_KEYS) if (repeat[key] != null) out[key] = repeat[key];
    return out;
}

// ---------------------------------------------------------------------------
// Field construction / patching
// ---------------------------------------------------------------------------

/** A new question from a spec (backend `_build_field`). */
export function buildField(spec: NewFieldSpec, index: number, newId: () => string): FormField {
    checkSpec(spec);
    if (!ADDABLE_FIELD_TYPES.has(spec.type)) throw new OpError(`Field type '${spec.type}' cannot be created by AI ops (allowed: ${sortedList(ADDABLE_FIELD_TYPES)}).`);
    const properties: Record<string, any> = { fields: [] };
    if (spec.type === FieldTypes.YES_NO) {
        properties.choices = [
            { id: newId(), value: 'Yes' },
            { id: newId(), value: 'No' }
        ];
    } else if (CHOICE_FIELD_TYPES.has(spec.type)) {
        if (!spec.choices || spec.choices.length < 2) throw new OpError(`'${spec.type}' needs at least 2 choices.`);
        properties.choices = spec.choices.map((value) => ({ id: newId(), value }));
        if (spec.allowMultiple && spec.type === FieldTypes.MULTIPLE_CHOICE) properties.allowMultipleSelection = true;
    } else if (RATING_FIELD_TYPES.has(spec.type)) {
        properties.steps = spec.steps || (spec.type === FieldTypes.RATING ? 5 : 10);
        if (spec.startFrom != null) properties.startFrom = spec.startFrom;
    }
    if (spec.placeholder != null) properties.placeholder = spec.placeholder;
    if (spec.description != null) properties.description = spec.description;
    if (spec.colSpan != null) properties.colSpan = spec.colSpan;
    if (spec.whyWeAsk && spec.whyWeAsk.trim()) properties.whyWeAsk = spec.whyWeAsk.trim();
    if (spec.label) {
        if (spec.type !== FieldTypes.DATE) throw new OpError('A label only applies to date questions.');
        properties.label = spec.label;
    }
    const validations = spec.required != null ? { required: spec.required } : {};
    if (spec.internal) ensureCanBeInternal(spec.type);
    const field: FormField = { id: newId(), index, type: spec.type, title: spec.title, properties, validations };
    if (spec.description != null) field.description = spec.description;
    if (spec.internal) field.internal = true;
    return field;
}

/** Apply a partial update (backend `_patch_field`); returns the change fragments. */
function patchField(target: Draft<FormField>, plain: FormField, patch: FieldPatch, newId: () => string): string[] {
    const changed: string[] = [];
    const properties = ensureProperties(target);
    if (target.validations == null) target.validations = {};
    const type: string = plain.type;

    if (patch.title != null) {
        target.title = patch.title as any;
        changed.push('title');
    }
    if (patch.description != null) {
        target.description = patch.description;
        (properties as any).description = patch.description;
        changed.push('description');
    }
    if (patch.required != null) {
        target.validations!.required = patch.required;
        changed.push(patch.required ? 'required' : 'optional');
    }
    if (patch.placeholder != null) {
        properties.placeholder = patch.placeholder;
        changed.push('placeholder');
    }
    if (patch.choices != null) {
        if (type === FieldTypes.YES_NO) throw new OpError('Yes/No choices are fixed — convert the field instead.');
        if (!CHOICE_FIELD_TYPES.has(type)) throw new OpError(`'${type || 'unknown'}' has no choices to update.`);
        if (patch.choices.length < 2) throw new OpError('A choice field needs at least 2 choices.');
        // Keep the ids of unchanged values so existing logic rules survive.
        const existing = new Map<string, any>();
        for (const choice of plain.properties?.choices ?? []) if (choice.value) existing.set(choice.value, choice);
        properties.choices = patch.choices.map((value) => existing.get(value) ?? { id: newId(), value });
        changed.push('choices');
    }
    if (patch.steps != null) {
        if (!RATING_FIELD_TYPES.has(type)) throw new OpError("'steps' only applies to rating fields.");
        if (patch.steps < 1) throw new OpError("'steps' must be a positive integer.");
        properties.steps = patch.steps;
        changed.push('steps');
    }
    if (patch.startFrom != null) {
        properties.startFrom = patch.startFrom;
        changed.push('startFrom');
    }
    if (patch.colSpan != null) {
        properties.colSpan = patch.colSpan;
        changed.push('width');
    }
    if (patch.whyWeAsk != null) {
        setKey(properties, 'whyWeAsk', patch.whyWeAsk.trim() || undefined);
        changed.push('why we ask this');
    }
    if (patch.internal) ensureCanBeInternal(type);
    if (patch.internal != null) {
        setKey(target, 'internal', patch.internal ? true : undefined);
        changed.push(patch.internal ? 'internal' : 'respondent-facing');
    }
    if (patch.label != null) {
        if (type !== FieldTypes.DATE) throw new OpError('A label only applies to date questions.');
        setKey(properties, 'label', patch.label.trim() || undefined);
        changed.push('label');
    }
    if (patch.dateRules != null) {
        // checked against the form by updateField beforehand
        const rules = checkedDateRules(patch.dateRules);
        setKey(properties, 'dateRules', rules.length ? rules : undefined);
        changed.push('date rules');
    }
    const groupPatch: Record<string, any> = {};
    for (const key of REPEAT_KEYS) if (patch[key] != null) groupPatch[key] = patch[key];
    const groupKeys = Object.keys(groupPatch) as Array<(typeof REPEAT_KEYS)[number]>;
    if (groupKeys.length) {
        if (!isRepeatingGroup(plain)) throw new OpError('Item limits and labels only apply to repeating groups.');
        const merged = { ...(plain.properties!.repeat as Record<string, any>), ...groupPatch };
        const problem = repeatProblems(merged);
        if (problem) throw new OpError(problem);
        properties.repeat = compactRepeat(merged);
        changed.push(...groupKeys.map((key) => REPEAT_KEY_LABELS[key]));
    }
    if (!changed.length) throw new OpError('The update contained no changes.');
    return changed;
}

function insertPosition(fields: FormField[], afterFieldId: string | null | undefined, index: number | null | undefined, where: string): number {
    if (afterFieldId != null) {
        const position = fields.findIndex((f) => f.id === afterFieldId);
        if (position < 0) throw new OpError(`Field '${afterFieldId}' is not in ${where}.`);
        return position + 1;
    }
    if (index != null) return Math.max(0, Math.min(index, fields.length));
    return fields.length;
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

export const addField: Handler<AddFieldOp> = (ctx, op) => {
    if (op.groupId != null) {
        const group = findGroup(ctx.state, op.groupId);
        checkChildType(op.field.type, op.field.internal);
        const children = childrenOf(group.field);
        const at = insertPosition(children, op.afterFieldId, op.index, `group '${op.groupId}'`);
        const child = buildField(op.field, at, ctx.newId);
        setFields(draftField(ctx.draft, group), insertedAt(children, at, child));
        ctx.noteCreated(child.id);
        return `Added '${op.field.title}' (${op.field.type}) to the group '${titleText(group.field)}'`;
    }
    if (op.pageId == null) throw new OpError('add_field needs a pageId (or a groupId to add into a repeating group).');
    const { page, pos } = findPage(ctx.state, op.pageId);
    const pageDraft = ctx.draft.fields![pos];
    ensureFields(pageDraft);
    const at = insertPosition(childrenOf(page), op.afterFieldId, op.index, `page '${op.pageId}'`);
    const field = buildField(op.field, at, ctx.newId);
    setFields(pageDraft, insertedAt(childrenOf(page), at, field));
    ctx.noteCreated(field.id);
    return `Added '${op.field.title}' (${op.field.type}) to page ${page.index != null ? page.index + 1 : '?'}`;
};

/** Ids of every field some respondent logic (visibility or jump) reads. */
export function logicSources(doc: FormDoc): Set<string | undefined> {
    const sources = new Set<string | undefined>();
    for (const page of pagesOf(doc)) {
        for (const jump of page.properties?.jumps ?? []) for (const c of jump.conditions ?? []) sources.add(c.fieldId);
        for (const field of childrenOf(page)) {
            const questions = [field, ...(isRepeatingGroup(field) ? childrenOf(field) : [])];
            for (const question of questions) {
                for (const c of question.properties?.logic?.conditions ?? []) {
                    sources.add(c.fieldId);
                    if (c.childFieldId) sources.add(c.childFieldId);
                }
            }
        }
    }
    for (const page of pagesOf(doc)) for (const jump of page.properties?.jumps ?? []) for (const c of jump.conditions ?? []) if (c.childFieldId) sources.add(c.childFieldId);
    return sources;
}

export const addGroup: Handler<AddGroupOp> = (ctx, op) => {
    const { page, pos } = findPage(ctx.state, op.pageId);
    const pageDraft = ctx.draft.fields![pos];
    ensureFields(pageDraft);
    const itemLabel = op.itemLabel ?? 'Item';
    const repeat = { minItems: op.minItems ?? 1, maxItems: op.maxItems ?? 3, itemLabel, itemTitle: op.itemTitle, exportLayout: op.exportLayout };
    const problem = repeatProblems(repeat);
    if (problem) throw new OpError(problem);
    const children = (op.fields ?? []).map((spec, i) => {
        checkChildType(spec.type, spec.internal);
        return buildField(spec, i, ctx.newId);
    });
    const at = insertPosition(childrenOf(page), op.afterFieldId, op.index, `page '${op.pageId}'`);
    const properties: Record<string, any> = { fields: children, repeat: compactRepeat(repeat) };
    if (op.description != null) properties.description = op.description;
    const group: FormField = { id: ctx.newId(), index: at, type: FieldTypes.GROUP, title: op.title, properties, validations: {} };
    if (op.description != null) group.description = op.description;
    setFields(pageDraft, insertedAt(childrenOf(page), at, group));
    ctx.noteCreated(
        group.id,
        children.map((child) => child.id)
    );
    return `Added the repeating group '${op.title}' (${repeat.minItems}-${repeat.maxItems} x ${itemLabel}, ${children.length} question(s)) as '${group.id}'`;
};

export const updateField: Handler<UpdateFieldOp> = (ctx, op) => {
    const location = locateField(ctx.state, op.fieldId);
    const { parent, field } = location;
    const patch = op.patch ?? {};
    checkTitle(patch.title);
    checkColSpan(patch.colSpan);
    checkMaxLength(patch.label, LABEL_MAX_LENGTH);
    checkMaxLength(patch.whyWeAsk, WHY_WE_ASK_MAX_LENGTH);
    if (patch.internal && parent !== null) throw new OpError(INTERNAL_IN_GROUP_MESSAGE);
    if (patch.internal && logicSources(ctx.state).has(op.fieldId)) {
        throw new OpError(`'${titleText(field)}' is used by conditional logic, so it cannot become internal — respondents never answer internal fields. Remove the rule first.`);
    }
    if (patch.internal && dateRuleSources(ctx.state.fields).has(op.fieldId)) {
        throw new OpError(`'${titleText(field)}' is used by a date rule, so it cannot become internal — respondents never answer internal fields. Remove the rule first.`);
    }
    if (patch.dateRules != null) {
        if (field.type !== FieldTypes.DATE) throw new OpError('Date rules only apply to date questions.');
        const rules = checkedDateRules(patch.dateRules);
        const known = new Set(dateRuleProblems(ctx.state.fields));
        const problems = dateRuleProblems(ctx.state.fields, { field, rules }).filter((p) => !known.has(p));
        if (problems.length) throw new OpError(problems[0]);
    }
    const changed = patchField(draftField(ctx.draft, location), field, patch, ctx.newId);
    const title = patch.title != null ? titleText({ ...field, title: patch.title } as FormField) : titleText(field);
    return `Updated '${title}' (${changed.join(', ')})`;
};

export const removeField: Handler<RemoveFieldOp> = (ctx, op) => {
    const location = locateField(ctx.state, op.fieldId);
    setFields(draftOwner(ctx.draft, location), removedAt(location.container, location.position));
    return `Removed '${titleText(location.field)}'${droppedRulesNote()}${droppedReferencesNote()}`;
};

export const moveField: Handler<MoveFieldOp> = (ctx, op) => {
    const location = locateField(ctx.state, op.fieldId);
    const { page, parent, field } = location;
    // the page or group the question goes to: its plain self and its draft
    let target: FormField;
    let targetDraft: () => Draft<FormField>;
    let where: string | null;
    if (op.toGroupId != null) {
        const group = findGroup(ctx.state, op.toGroupId);
        if (group.field === field) throw new OpError('A group cannot be moved into itself.');
        checkChildType(field.type, field.internal);
        target = group.field;
        targetDraft = () => draftField(ctx.draft, group);
        where = `the group '${titleText(group.field)}'`;
    } else if (op.toPageId != null || parent === null) {
        const targetPage = op.toPageId ? findPage(ctx.state, op.toPageId) : { page, pos: location.pagePos };
        target = targetPage.page;
        targetDraft = () => ctx.draft.fields![targetPage.pos];
        where = targetPage.page !== page || parent !== null ? `page ${targetPage.page.index != null ? targetPage.page.index + 1 : '?'}` : null;
    } else {
        target = parent; // reorder within its group
        targetDraft = () => draftOwner(ctx.draft, location);
        where = null;
    }
    const owner = parent ?? page;
    const source = removedAt(location.container, location.position);
    const targetList = target === owner ? source : childrenOf(target);
    const at = op.index == null ? targetList.length : Math.max(0, Math.min(op.index, targetList.length));
    if (target === owner) {
        setFields(draftOwner(ctx.draft, location), insertedAt(source, at, field));
    } else if (source.includes(target)) {
        // into a group of the same page: the page's new list holds the group's draft
        const groupDraft = targetDraft();
        setFields(groupDraft, insertedAt(targetList, at, field));
        setFields(
            draftOwner(ctx.draft, location),
            source.map((f) => (f === target ? groupDraft : f))
        );
    } else if (targetList.includes(owner)) {
        // out of a group onto its own page: likewise
        const groupDraft = draftOwner(ctx.draft, location);
        setFields(groupDraft, source);
        setFields(
            targetDraft(),
            insertedAt(targetList, at, field).map((f) => (f === owner ? groupDraft : f))
        );
    } else {
        setFields(draftOwner(ctx.draft, location), source);
        setFields(targetDraft(), insertedAt(targetList, at, field));
    }
    // In or out of a repeating group: rules across the boundary don't apply.
    const note = droppedRulesNote();
    if (where === null) return `Moved '${titleText(field)}' to position ${at + 1}${note}`;
    return `Moved '${titleText(field)}' to ${where}${note}`;
};

// ---------------------------------------------------------------------------
// Answer rules
// ---------------------------------------------------------------------------

export const VALIDATION_PRESETS: Record<string, string> = {
    digits: '^[0-9]+$',
    letters: "^[A-Za-zÀ-ɏ' -]+$",
    alphanumeric: '^[A-Za-z0-9]+$'
};

const LENGTH_TYPES = new Set<string>([FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT]);
const PATTERN_TYPES = new Set<string>([FieldTypes.SHORT_TEXT]);
const VALUE_TYPES = new Set<string>([FieldTypes.NUMBER]);
const VALIDATION_KEYS = ['required', 'minLength', 'maxLength', 'minValue', 'maxValue', 'minChoices', 'maxChoices', 'pattern', 'preset'];

function ruleApplies(field: FormField, types: Set<string>, rule: string, kinds: string): void {
    if (!types.has(field.type)) throw new OpError(`${rule} only apply to ${kinds} questions; '${titleText(field)}' is a ${field.type || 'unknown'} question.`);
}

/**
 * The spec's pattern rule (common `checked_pattern`): trimmed, not empty, at
 * most PATTERN_MAX_LENGTH characters, compiles. JavaScript's RegExp stands in
 * for Python's `re`; the few patterns one accepts and the other refuses are
 * refused by the server.
 */
export function checkedPattern(pattern: string): string {
    const trimmed = pattern.trim();
    if (!trimmed) throw new OpError('The pattern is empty: give a regular expression, or none.');
    if (pyLen(trimmed) > PATTERN_MAX_LENGTH) throw new OpError(`A pattern can be at most ${PATTERN_MAX_LENGTH} characters.`);
    try {
        new RegExp(trimmed, 'u');
    } catch (error) {
        throw new OpError(`'${trimmed}' is not a valid pattern (${(error as Error).message}).`);
    }
    return trimmed;
}

export const setFieldValidation: Handler<SetFieldValidationOp> = (ctx, op) => {
    const location = locateField(ctx.state, op.fieldId);
    const { field } = location;
    const patch: Record<string, any> = op.validation ?? {};
    const given = new Set(Object.keys(patch).filter((key) => VALIDATION_KEYS.includes(key)));
    if (!given.size) throw new OpError('Nothing to change — give at least one of: required, minLength, maxLength, minValue, maxValue, minChoices, maxChoices, pattern, preset.');
    if (patch.pattern != null && patch.preset != null) throw new OpError('Give either a pattern or a preset, not both.');
    // Work on a copy: a refused rule leaves the question as it was.
    const rules: Record<string, any> = { ...(field.validations ?? {}) };
    const changed: string[] = [];
    const set = (key: string, value: any) => {
        if (value == null) delete rules[key];
        else rules[key] = value;
    };

    if (given.has('required')) {
        set('required', patch.required);
        changed.push(patch.required ? 'required' : 'optional');
    }
    for (const [key, label] of [
        ['minLength', 'minimum length'],
        ['maxLength', 'maximum length']
    ]) {
        if (!given.has(key)) continue;
        ruleApplies(field, LENGTH_TYPES, 'Text lengths', 'short or long text');
        if (patch[key] != null && patch[key] < 0) throw new OpError(`The ${label} cannot be negative.`);
        set(key, patch[key]);
        changed.push(label);
    }
    for (const [key, label] of [
        ['minValue', 'minimum'],
        ['maxValue', 'maximum']
    ]) {
        if (!given.has(key)) continue;
        ruleApplies(field, VALUE_TYPES, 'Minimum and maximum values', 'number');
        set(key, patch[key]);
        changed.push(label);
    }
    for (const [key, label] of [
        ['minChoices', 'minimum choices'],
        ['maxChoices', 'maximum choices']
    ]) {
        if (!given.has(key)) continue;
        const value = patch[key];
        if (field.type !== FieldTypes.MULTIPLE_CHOICE || !field.properties?.allowMultipleSelection) {
            throw new OpError(`A number of choices only applies to a multiple choice question that allows several answers; '${titleText(field)}' does not.`);
        }
        if (value != null) {
            const available = (field.properties?.choices ?? []).length;
            if (value < (key === 'maxChoices' ? 1 : 0)) throw new OpError(`The ${label} must be a positive number.`);
            if (value > available) throw new OpError(`'${titleText(field)}' has ${available} choice(s), so the ${label} cannot be ${value}.`);
        }
        set(key, value);
        changed.push(label);
    }
    if (given.has('pattern') || given.has('preset')) {
        ruleApplies(field, PATTERN_TYPES, 'Patterns', 'short text');
        if (patch.preset != null) {
            set('regex', VALIDATION_PRESETS[patch.preset]);
            changed.push(`pattern (${patch.preset})`);
        } else if (patch.pattern != null) {
            set('regex', checkedPattern(patch.pattern));
            changed.push('pattern');
        } else {
            set('regex', undefined);
            changed.push('no pattern');
        }
    }
    for (const [low, high, what] of [
        ['minLength', 'maxLength', 'minimum length'],
        ['minValue', 'maxValue', 'minimum'],
        ['minChoices', 'maxChoices', 'minimum number of choices']
    ]) {
        const lo = rules[low];
        const hi = rules[high];
        if (lo != null && hi != null && lo > hi) throw new OpError(`The ${what} (${pyG(lo)}) cannot be more than the maximum (${pyG(hi)}).`);
    }
    draftField(ctx.draft, location).validations = rules;
    return `Updated the answer rules of '${titleText(field)}' (${changed.join(', ')})`;
};

// ---------------------------------------------------------------------------
// Visibility logic and the conditions page jumps share with it
// ---------------------------------------------------------------------------

export const VALUELESS_COMPARISONS = new Set(['IS_EMPTY', 'IS_NOT_EMPTY']);
const COUNT_COMPARISONS = new Set(['IS_EQUAL', 'IS_NOT_EQUAL', 'GREATER_THAN', 'GREATER_THAN_EQUAL', 'LESS_THAN', 'LESS_THAN_EQUAL']);

function validatedValue(source: FormField, comparison: string, raw: any): any {
    if (VALUELESS_COMPARISONS.has(comparison)) return undefined;
    if (raw === null || raw === undefined || raw === '') throw new OpError(`Comparison '${comparison}' needs a value.`);
    if (CHOICE_FIELD_TYPES.has(source.type)) {
        const labels = (source.properties?.choices ?? []).map((c: any) => c.value);
        if (!labels.includes(pyStr(raw))) throw new OpError(`'${pyStr(raw)}' is not a choice of '${titleText(source)}'. Choices: ${labels.join(', ')}`);
    }
    if (source.type === FieldTypes.YES_NO && pyStr(raw) !== 'Yes' && pyStr(raw) !== 'No') throw new OpError("Yes/No conditions take the value 'Yes' or 'No'.");
    return raw;
}

/** Python's `int(value)` for the values a count condition may carry, or null. */
function pyInt(value: any): number | null {
    if (typeof value === 'boolean') return value ? 1 : 0;
    if (typeof value === 'number') return Number.isFinite(value) ? Math.trunc(value) : null;
    if (typeof value === 'string' && /^\s*[+-]?\d+\s*$/.test(value)) return parseInt(value, 10);
    return null;
}

/** Resolve and check condition sources against the form (backend `_validated_conditions`). */
export function validatedConditions(doc: FormDoc, specs: LogicConditionSpec[], scopeGroupId: string | null = null): Record<string, any>[] {
    const conditions: Record<string, any>[] = [];
    for (const spec of specs) {
        const { parent, field: source } = locateField(doc, spec.fieldId);
        if (source.internal) throw new OpError(`'${titleText(source)}' is an internal field — respondents never answer it, so logic cannot depend on it.`);
        if (parent !== null && parent.id !== scopeGroupId) {
            throw new OpError(`'${titleText(source)}' is asked once per item of '${titleText(parent)}'. Outside the group, refer to the group itself with groupMode COUNT, ANY or ALL.`);
        }
        if (isRepeatingGroup(source)) {
            if (spec.groupMode == null) throw new OpError(`'${titleText(source)}' is a repeating group: set groupMode to COUNT (number of items), ANY or ALL (with childFieldId).`);
            if (spec.groupMode === 'COUNT') {
                if (!COUNT_COMPARISONS.has(spec.comparison)) throw new OpError('Item-count conditions compare a number (e.g. IS_EQUAL, GREATER_THAN_EQUAL).');
                const count = pyInt(spec.value);
                if (count === null) throw new OpError('Item-count conditions need a whole number as value.');
                conditions.push({ fieldId: spec.fieldId, fieldType: source.type, comparison: spec.comparison, value: count, groupMode: 'COUNT' });
                continue;
            }
            const child = childrenOf(source).find((c) => c.id === spec.childFieldId);
            if (!child) throw new OpError(`ANY/ALL conditions need childFieldId: a question of '${titleText(source)}'.`);
            const condition: Record<string, any> = { fieldId: spec.fieldId, fieldType: source.type, comparison: spec.comparison };
            const value = validatedValue(child, spec.comparison, spec.value);
            if (value !== undefined) condition.value = value;
            Object.assign(condition, { groupMode: spec.groupMode, childFieldId: child.id, childFieldType: child.type });
            conditions.push(condition);
            continue;
        }
        if (spec.groupMode != null) throw new OpError(`groupMode only applies to repeating groups, not '${titleText(source)}'.`);
        const condition: Record<string, any> = { fieldId: spec.fieldId, fieldType: source.type, comparison: spec.comparison };
        const value = validatedValue(source, spec.comparison, spec.value);
        if (value !== undefined) condition.value = value;
        conditions.push(condition);
    }
    return conditions;
}

export const setFieldLogic: Handler<SetFieldLogicOp> = (ctx, op) => {
    const location = locateField(ctx.state, op.fieldId);
    const { parent, field } = location;
    const target = draftField(ctx.draft, location);
    const properties = ensureProperties(target, false);
    if (op.logic == null) {
        setKey(properties, 'logic', undefined);
        return `Cleared the visibility rule on '${titleText(field)}'`;
    }
    if (!op.logic.conditions?.length) throw new OpError('List should have at least 1 item after validation, not 0');
    for (const spec of op.logic.conditions) if (spec.fieldId === op.fieldId) throw new OpError("A field's visibility cannot depend on its own answer.");
    const conditions = validatedConditions(ctx.state, op.logic.conditions, parent ? parent.id : null);
    properties.logic = { action: op.logic.action, operator: op.logic.operator ?? 'AND', conditions } as any;
    const verb = op.logic.action === 'SHOW' ? 'Show' : 'Hide';
    return `${verb} '${titleText(field)}' when ${conditions.length} condition(s) match`;
};
