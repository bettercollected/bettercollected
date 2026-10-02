import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { DateRule, DateRuleComparison } from '@app/models/types/form-builder-shared';
import { isFieldHiddenByLogic } from '@app/utils/conditional-logic';
import { getGroupChildren, getGroupItems, getItemHiddenChildIds, isRepeatingGroup, itemScopeAnswers, plainTitle, scopedFieldId } from '@app/utils/repeating-groups';

/**
 * Date rules — constraints on a date question's answer, stored at
 * `properties.dateRules`: the chosen date must be before / after / on or
 * before / on or after a fixed date, today, or the answer of another date
 * question ("End date must be after Start date").
 *
 * - Dates are calendar dates (`YYYY-MM-DD`) compared as such, never as
 *   instants; "today" is the respondent's local day.
 * - A rule on another question applies only when that question is answered
 *   and not hidden by logic.
 * - Inside a repeating group a rule may only use a sibling of the same group
 *   and then compares the answers of the same item; outside a group, a rule
 *   never uses a group's questions.
 *
 * The backend enforces the same rules on submit and on response edits
 * (backend/app/services/date_rules.py) and validates references on save
 * (`date_rule_problems` in common/models/standard_form.py) — keep them in step.
 */

/** At most this many rules per date question (mirrors the backend). */
export const DATE_RULES_MAX = 5;

export const DATE_RULE_COMPARISON_LABELS: Record<DateRuleComparison, string> = {
    before: 'before',
    after: 'after',
    on_or_before: 'on or before',
    on_or_after: 'on or after'
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Is `value` a real calendar date written exactly as YYYY-MM-DD? */
export function isIsoDate(value: unknown): value is string {
    if (typeof value !== 'string') return false;
    const match = ISO_DATE.exec(value);
    if (!match) return false;
    const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
    const date = new Date(Date.UTC(year, month - 1, day));
    return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

/** The local calendar day of `date` as YYYY-MM-DD (no time-zone shift). */
export function toIsoDate(date: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** The respondent's today, as YYYY-MM-DD. */
export function todayIso(now: Date = new Date()): string {
    return toIsoDate(now);
}

/** YYYY-MM-DD → a local Date at midnight (`new Date('YYYY-MM-DD')` would be UTC). */
export function isoToLocalDate(value: string): Date | undefined {
    if (!isIsoDate(value)) return undefined;
    const [year, month, day] = value.split('-').map(Number);
    return new Date(year, month - 1, day);
}

/** `2026-03-12` → `12 Mar 2026` (same wording as the backend's messages). */
export function formatIsoDate(value: string): string {
    if (!isIsoDate(value)) return value;
    const [year, month, day] = value.split('-').map(Number);
    return `${day} ${MONTHS[month - 1]} ${year}`;
}

/** Does the date `value` break "must be <comparison> `bound`"? Both YYYY-MM-DD. */
export function isDateRuleViolated(value: string, comparison: DateRuleComparison, bound: string): boolean {
    switch (comparison) {
        case 'before':
            return !(value < bound);
        case 'after':
            return !(value > bound);
        case 'on_or_before':
            return !(value <= bound);
        case 'on_or_after':
            return !(value >= bound);
        default:
            return false;
    }
}

export function getDateRules(field: StandardFormFieldDto | undefined): DateRule[] {
    return field?.type === FieldTypes.DATE ? (field.properties?.dateRules ?? []) : [];
}

export interface DateRuleContext {
    /** Answers as seen by the question (inside a group item: the item's scope). */
    answers: Record<string, any>;
    /** Questions by id, group questions included (`getInputFieldsById`). */
    fieldsById: Record<string, StandardFormFieldDto>;
    /** The respondent's today, YYYY-MM-DD. */
    today: string;
}

/** A rule that applies right now, with the date it compares against. */
export interface DateRuleBound {
    rule: DateRule;
    bound: string;
    /** "Start date (12 Mar 2026)", "today (2 Oct 2026)" or "12 Mar 2026". */
    label: string;
}

/** What the canvas shows for a date question without a title of its own. */
const DATE_TITLE_PLACEHOLDER = 'Select a date';

/** The question's own title text ('' when it has none: new questions show a placeholder). */
function ownTitle(field: StandardFormFieldDto | undefined): string {
    const title = plainTitle(field);
    return title === 'Untitled question' ? '' : title;
}

/** A date question as the builder lists it: the text the canvas shows for it. */
export function dateQuestionTitle(field: StandardFormFieldDto | undefined): string {
    return ownTitle(field) || DATE_TITLE_PLACEHOLDER;
}

/** Short name of a date question in messages: its label, else its title, else a neutral phrase. */
export function dateFieldName(field: StandardFormFieldDto | undefined): string {
    const label = field?.properties?.label?.trim();
    return label || ownTitle(field) || 'the other date';
}

/** The field's rules that apply given the answers so far, with their bounds. */
export function resolveDateRuleBounds(field: StandardFormFieldDto, context: DateRuleContext): DateRuleBound[] {
    const bounds: DateRuleBound[] = [];
    getDateRules(field).forEach((rule) => {
        if (rule.target === 'date') {
            if (isIsoDate(rule.date)) bounds.push({ rule, bound: rule.date, label: formatIsoDate(rule.date) });
        } else if (rule.target === 'today') {
            bounds.push({ rule, bound: context.today, label: `today (${formatIsoDate(context.today)})` });
        } else if (rule.target === 'field' && rule.fieldId) {
            const source = context.fieldsById[rule.fieldId];
            // Unanswered, hidden by logic or gone: the rule does not apply.
            if (!source || source.type !== FieldTypes.DATE || isFieldHiddenByLogic(source, context.answers)) return;
            const value = context.answers?.[rule.fieldId]?.date;
            if (!isIsoDate(value)) return;
            bounds.push({ rule, bound: value, label: `${dateFieldName(source)} (${formatIsoDate(value)})` });
        }
    });
    return bounds;
}

export function describeDateRuleViolation(violation: DateRuleBound): string {
    return `Must be ${DATE_RULE_COMPARISON_LABELS[violation.rule.comparison]} ${violation.label}.`;
}

/** The rules a date `value` breaks. */
export function getDateRuleViolations(field: StandardFormFieldDto, value: string, context: DateRuleContext): DateRuleBound[] {
    return resolveDateRuleBounds(field, context).filter((b) => isDateRuleViolated(value, b.rule.comparison, b.bound));
}

/**
 * The message to show under a date question right now, if its answer breaks
 * one of its rules (or is not a date at all, e.g. a bad URL prefill).
 * `answerId` is the key the answer is stored under (the scoped id inside a
 * repeating group item).
 */
export function getDateRuleError(field: StandardFormFieldDto, context: DateRuleContext, answerId: string = field.id): string | undefined {
    if (!getDateRules(field).length) return undefined;
    const value = context.answers?.[answerId]?.date;
    if (value === undefined || value === null || value === '') return undefined;
    if (!isIsoDate(value)) return 'Please pick a valid date.';
    const [first] = getDateRuleViolations(field, value, context);
    return first ? describeDateRuleViolation(first) : undefined;
}

/** A day-picker matcher: true for the days the field's rules rule out. */
export function getDisabledDayMatcher(field: StandardFormFieldDto, context: DateRuleContext): ((day: Date) => boolean) | undefined {
    const bounds = resolveDateRuleBounds(field, context);
    if (!bounds.length) return undefined;
    return (day: Date) => {
        const value = toIsoDate(day);
        return bounds.some((b) => isDateRuleViolated(value, b.rule.comparison, b.bound));
    };
}

export type DateRuleInvalidation = 'DATE_RULE';

/** Date questions among `fields` (top level of a page) whose answer breaks a rule. */
export function validateDateRulesInFields(fields: Array<StandardFormFieldDto> | undefined, answers: Record<string, any>, fieldsById: Record<string, StandardFormFieldDto>, today: string): Record<string, DateRuleInvalidation[]> {
    const invalid: Record<string, DateRuleInvalidation[]> = {};
    (fields ?? []).forEach((field) => {
        if (getDateRuleError(field, { answers, fieldsById, today })) invalid[field.id] = ['DATE_RULE'];
    });
    return invalid;
}

/** Per item of a repeating group: date questions whose answer breaks a rule (keyed by the scoped id). */
export function validateGroupDateRules(group: StandardFormFieldDto, answers: Record<string, any>, fieldsById: Record<string, StandardFormFieldDto>, today: string): Record<string, DateRuleInvalidation[]> {
    const invalid: Record<string, DateRuleInvalidation[]> = {};
    const children = getGroupChildren(group);
    const ruled = children.filter((child) => getDateRules(child).length);
    if (!ruled.length) return invalid;
    const childIds = children.map((c) => c.id);
    getGroupItems(answers, group.id).forEach((_item, index) => {
        const scoped = itemScopeAnswers(answers, { groupId: group.id, index, childIds });
        const hidden = getItemHiddenChildIds(group, answers, index);
        ruled.forEach((child) => {
            if (hidden.has(child.id)) return;
            if (getDateRuleError(child, { answers: scoped, fieldsById, today })) invalid[scopedFieldId(child.id, index)] = ['DATE_RULE'];
        });
    });
    return invalid;
}

/** All date-rule problems among a page's visible fields (top level and repeating groups). */
export function validateDateRulesInSlide(fields: Array<StandardFormFieldDto> | undefined, answers: Record<string, any>, fieldsById: Record<string, StandardFormFieldDto>, today: string = todayIso()): Record<string, DateRuleInvalidation[]> {
    return (fields ?? []).reduce(
        (acc, field) => ({ ...acc, ...(isRepeatingGroup(field) ? validateGroupDateRules(field, answers, fieldsById, today) : validateDateRulesInFields([field], answers, fieldsById, today)) }),
        {} as Record<string, DateRuleInvalidation[]>
    );
}

// ---------------------------------------------------------------------------
// Builder helpers
// ---------------------------------------------------------------------------

interface ScopedQuestion {
    field: StandardFormFieldDto;
    /** The repeating group the question belongs to, if any. */
    groupId?: string;
}

function questionsByScope(slides: Array<StandardFormFieldDto>): Record<string, ScopedQuestion> {
    const byId: Record<string, ScopedQuestion> = {};
    (slides ?? []).forEach((slide) =>
        slide?.properties?.fields?.forEach((field) => {
            if (field?.id) byId[field.id] = { field };
            if (isRepeatingGroup(field)) getGroupChildren(field).forEach((child) => child?.id && (byId[child.id] = { field: child, groupId: field.id }));
        })
    );
    return byId;
}

/** Could `owner` use `source` in a rule: a respondent-facing date question of the same scope, not itself. */
function isUsableSource(owner: ScopedQuestion, source: ScopedQuestion | undefined): boolean {
    return !!source && source.field !== owner.field && source.field.type === FieldTypes.DATE && !source.field.internal && source.groupId === owner.groupId;
}

/**
 * Sweep date rules a structural edit left dangling — the question they use
 * was removed, made internal, or moved in or out of a repeating group — and
 * the rules of questions that are no longer dates. Mutates in place (the
 * date-rule counterpart of `pruneOrphanedConditions`; backend twin:
 * `prune_date_rules`).
 */
export function pruneOrphanedDateRules(slides: Array<StandardFormFieldDto>): Array<StandardFormFieldDto> {
    const byId = questionsByScope(slides);
    Object.values(byId).forEach((owner) => {
        const rules = owner.field.properties?.dateRules;
        if (!rules) return;
        const kept = owner.field.type === FieldTypes.DATE ? rules.filter((rule) => rule.target !== 'field' || (!!rule.fieldId && isUsableSource(owner, byId[rule.fieldId]))) : [];
        if (kept.length) owner.field.properties!.dateRules = kept;
        else delete owner.field.properties!.dateRules;
    });
    return slides;
}

/** Point copied date rules at the copies of the questions they used (`idMap`: old id → new id). */
export function remapDateRules(fields: Array<StandardFormFieldDto> | undefined, idMap: Record<string, string>): void {
    (fields ?? []).forEach((field) =>
        field?.properties?.dateRules?.forEach((rule) => {
            if (rule.fieldId && idMap[rule.fieldId]) rule.fieldId = idMap[rule.fieldId];
        })
    );
}

/** Would a rule "owner uses candidate" close a circle (candidate already depends on owner)? */
export function wouldCreateDateRuleCycle(slides: Array<StandardFormFieldDto>, ownerId: string, candidateId: string): boolean {
    const byId = questionsByScope(slides);
    const seen = new Set<string>();
    const stack = [candidateId];
    while (stack.length) {
        const id = stack.pop()!;
        if (id === ownerId) return true;
        if (seen.has(id)) continue;
        seen.add(id);
        getDateRules(byId[id]?.field).forEach((rule) => rule.target === 'field' && rule.fieldId && stack.push(rule.fieldId));
    }
    return false;
}

export interface DateRuleSource {
    id: string;
    label: string;
}

/**
 * The date questions a rule of `owner` may use, in form order: earlier date
 * questions of the same scope (the page level, or the same repeating group),
 * never the owner itself, never one that would close a circle of rules.
 */
export function getDateRuleSources(slides: Array<StandardFormFieldDto>, ownerId: string): DateRuleSource[] {
    const byId = questionsByScope(slides);
    const owner = byId[ownerId];
    if (!owner) return [];
    const ordered: ScopedQuestion[] = [];
    (slides ?? []).forEach((slide) =>
        slide?.properties?.fields?.forEach((field) => {
            ordered.push(byId[field.id] ?? { field });
            if (isRepeatingGroup(field)) getGroupChildren(field).forEach((child) => ordered.push(byId[child.id]));
        })
    );
    const position = ordered.findIndex((q) => q?.field === owner.field);
    const multiPage = (slides ?? []).length > 1;
    const pageOf = (id: string) => (slides ?? []).findIndex((slide) => slide?.properties?.fields?.some((f) => f.id === id || getGroupChildren(f).some((c) => c.id === id)));
    return ordered
        .slice(0, Math.max(position, 0))
        .filter((q) => q && isUsableSource(owner, q) && !wouldCreateDateRuleCycle(slides, ownerId, q.field.id))
        .map((q) => {
            const name = dateQuestionTitle(q.field);
            return { id: q.field.id, label: multiPage && !owner.groupId ? `Page ${pageOf(q.field.id) + 1} · ${name}` : name };
        });
}
