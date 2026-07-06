import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, FieldConditionalLogic, JUMP_TARGET_SUBMIT, LogicalOperator, LogicCondition, PageJump } from '@app/models/types/form-builder-shared';

export type { FieldConditionalLogic, LogicAction, LogicCondition, PageJump } from '@app/models/types/form-builder-shared';

/**
 * Conditional logic (v2 builder) — show/hide a question based on earlier answers.
 *
 * This is deliberately separate from the older `vvalidation-utils` engine, which
 * was written for the v1 builder: it keys comparisons off `FormBuilderTagNames`
 * and toggles whole slides, neither of which matches the v2 slide/field model.
 *
 * The rule lives on the *target* field at `field.properties.logic`:
 *   - `action: 'SHOW'` → the field is hidden until the conditions are met.
 *   - `action: 'HIDE'` → the field is visible until the conditions are met.
 * Conditions reference an earlier field's answer by id + type, so we can read the
 * right slot out of the stored answer.
 */

/** Pull the comparable value out of a stored v2 answer for a given source field type. */
export function getComparableAnswerValue(answer: any, fieldType: FieldTypes | string): any {
    if (!answer) return undefined;
    switch (fieldType) {
        case FieldTypes.YES_NO:
            return typeof answer.boolean === 'boolean' ? (answer.boolean ? 'Yes' : 'No') : undefined;
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LONG_TEXT:
            return answer.text;
        case FieldTypes.EMAIL:
            return answer.email ?? answer.text;
        case FieldTypes.LINK:
            return answer.url ?? answer.text;
        case FieldTypes.NUMBER:
        case FieldTypes.RATING:
        case FieldTypes.LINEAR_RATING:
            return answer.number;
        case FieldTypes.DATE:
            return answer.date;
        case FieldTypes.PHONE_NUMBER:
            return answer.phoneNumber ?? answer.phone_number;
        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN:
            // multi-select stores `choices.values`, single stores `choice.value`
            return answer.choices?.values ?? answer.choice?.value;
        default:
            return answer.text ?? answer.value;
    }
}

const isEmpty = (v: any): boolean => v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0);

const toNumber = (v: any): number => (Array.isArray(v) ? NaN : Number(v));

function evaluateCondition(answers: Record<string, any>, condition: LogicCondition): boolean {
    const value = getComparableAnswerValue(answers?.[condition.fieldId], condition.fieldType);
    const target = condition.value;

    switch (condition.comparison) {
        case Comparison.IS_EMPTY:
            return isEmpty(value);
        case Comparison.IS_NOT_EMPTY:
            return !isEmpty(value);
        case Comparison.IS_EQUAL:
            if (Array.isArray(value)) return value.map(String).includes(String(target));
            return String(value ?? '') === String(target ?? '');
        case Comparison.IS_NOT_EQUAL:
            if (Array.isArray(value)) return !value.map(String).includes(String(target));
            return String(value ?? '') !== String(target ?? '');
        case Comparison.CONTAINS:
            if (Array.isArray(value)) return value.map(String).includes(String(target));
            return String(value ?? '').toLowerCase().includes(String(target ?? '').toLowerCase());
        case Comparison.DOES_NOT_CONTAIN:
            if (Array.isArray(value)) return !value.map(String).includes(String(target));
            return !String(value ?? '').toLowerCase().includes(String(target ?? '').toLowerCase());
        case Comparison.GREATER_THAN:
            return toNumber(value) > toNumber(target);
        case Comparison.GREATER_THAN_EQUAL:
            return toNumber(value) >= toNumber(target);
        case Comparison.LESS_THAN:
            return toNumber(value) < toNumber(target);
        case Comparison.LESS_THAN_EQUAL:
            return toNumber(value) <= toNumber(target);
        case Comparison.STARTS_WITH:
            return String(value ?? '').toLowerCase().startsWith(String(target ?? '').toLowerCase());
        case Comparison.ENDS_WITH:
            return String(value ?? '').toLowerCase().endsWith(String(target ?? '').toLowerCase());
        default:
            return false;
    }
}

/** Fold a set of conditions with AND/OR. Empty/incomplete condition sets never match. */
export function evaluateConditions(operator: LogicalOperator | undefined, conditions: LogicCondition[] | undefined, answers: Record<string, any>): boolean {
    const valid = (conditions ?? []).filter((c) => c && c.fieldId && c.comparison);
    if (valid.length === 0) return false;
    if (operator === LogicalOperator.OR) return valid.some((c) => evaluateCondition(answers, c));
    return valid.every((c) => evaluateCondition(answers, c));
}

/** Are a rule's conditions satisfied given the current answers? */
export function areConditionsMet(logic: FieldConditionalLogic, answers: Record<string, any>): boolean {
    return evaluateConditions(logic?.operator, logic?.conditions, answers);
}

/**
 * Resolve where a slide should send the responder on "Next", given the answers.
 * Returns the first matching jump rule's target (a slide id or JUMP_TARGET_SUBMIT),
 * or null when no rule matches (caller falls back to the linear next page).
 */
export function resolveJumpTargetId(slide: StandardFormFieldDto | undefined, answers: Record<string, any>): string | null {
    const jumps = slide?.properties?.jumps as PageJump[] | undefined;
    if (!Array.isArray(jumps)) return null;
    for (const jump of jumps) {
        if (jump?.conditions?.length && evaluateConditions(jump.operator, jump.conditions, answers)) {
            return jump.target || null;
        }
    }
    return null;
}

/**
 * Is this field hidden right now given the answers so far?
 * Fields without a logic rule (or with no usable conditions) are always visible.
 */
export function isFieldHiddenByLogic(field: StandardFormFieldDto, answers: Record<string, any>): boolean {
    const logic = field?.properties?.logic as FieldConditionalLogic | undefined;
    if (!logic || !logic.action || !(logic.conditions?.length > 0)) return false;
    const met = areConditionsMet(logic, answers);
    return logic.action === 'SHOW' ? !met : met;
}

/** Ids of every field in a slide that should be hidden right now. */
export function getHiddenFieldIds(fields: Array<StandardFormFieldDto> | undefined, answers: Record<string, any>): Set<string> {
    const hidden = new Set<string>();
    fields?.forEach((field) => {
        if (isFieldHiddenByLogic(field, answers)) hidden.add(field.id);
    });
    return hidden;
}

/** Is a jump's target still a real destination (an existing slide, or "submit")? */
export function isJumpTargetValid(target: string | undefined, slideIds: Set<string>): boolean {
    return !!target && (target === JUMP_TARGET_SUBMIT || slideIds.has(target));
}

/** Does a field carry a usable conditional-visibility rule? */
export function fieldHasLogic(field: StandardFormFieldDto | undefined): boolean {
    return !!(field?.properties?.logic as FieldConditionalLogic | undefined)?.conditions?.length;
}

/** Does a slide carry any logic — page jumps, or a field with a visibility rule? */
export function slideHasLogic(slide: StandardFormFieldDto | undefined): boolean {
    const jumps = slide?.properties?.jumps as PageJump[] | undefined;
    if (jumps?.some((j) => j?.conditions?.length)) return true;
    return !!slide?.properties?.fields?.some((f) => fieldHasLogic(f));
}

/** Aggregated flow traffic replayed from submitted responses. */
export interface FlowTraffic {
    /** submissions counted */
    total: number;
    /** slide id → number of submissions whose path visited it */
    nodeVisits: Map<string, number>;
    /** `${slideId}:${jumpIndex}` → traversals of that jump edge */
    jumpTraversals: Map<string, number>;
    /** slide id (or '__welcome__') → times the linear "next" edge out of it was taken */
    nextTraversals: Map<string, number>;
}

/**
 * Replay the forward path a submission implies through the flow, using the SAME
 * jump resolution the responder ran. Approximation is explicit: we replay from
 * final answers, so mid-fill back-tracking isn't represented, and paths are
 * capped at 2×pages+2 hops in case persisted rules loop.
 */
export function computeFlowTraffic(slides: Array<StandardFormFieldDto>, answersList: Array<Record<string, any>>): FlowTraffic {
    const traffic: FlowTraffic = { total: answersList.length, nodeVisits: new Map(), jumpTraversals: new Map(), nextTraversals: new Map() };
    const slideIds = new Set(slides.map((s) => s.id));
    const indexById = new Map(slides.map((s, i) => [s.id, i]));
    const bump = (map: Map<string, number>, key: string) => map.set(key, (map.get(key) ?? 0) + 1);
    const maxHops = slides.length * 2 + 2;

    answersList.forEach((answers) => {
        bump(traffic.nextTraversals, '__welcome__'); // welcome → first page
        let index = 0;
        for (let hop = 0; hop < maxHops && index >= 0 && index < slides.length; hop++) {
            const slide = slides[index];
            bump(traffic.nodeVisits, slide.id);

            // Find the first matching jump (same order semantics as the responder).
            const jumps = (slide.properties?.jumps as PageJump[] | undefined) ?? [];
            const matchIdx = jumps.findIndex((j) => j?.conditions?.length && isJumpTargetValid(j.target, slideIds) && evaluateConditions(j.operator, j.conditions, answers ?? {}));
            if (matchIdx >= 0) {
                bump(traffic.jumpTraversals, `${slide.id}:${matchIdx}`);
                const target = jumps[matchIdx].target;
                if (target === JUMP_TARGET_SUBMIT) return;
                index = indexById.get(target) ?? -1;
                continue;
            }
            bump(traffic.nextTraversals, slide.id);
            index += 1;
        }
    });

    return traffic;
}

/**
 * Drop logic that can no longer evaluate after a page/question is deleted:
 * conditions pointing at fields that no longer exist (and any rule left with zero
 * conditions). Mutates the slide array in place and returns it. Jump targets that
 * point at a deleted page are left intact so the UI can surface them as broken
 * rather than silently rewriting where a rule sends people.
 */
export function pruneOrphanedConditions(slides: Array<StandardFormFieldDto>): Array<StandardFormFieldDto> {
    const fieldIds = new Set<string>();
    slides.forEach((slide) => slide?.properties?.fields?.forEach((f) => fieldIds.add(f.id)));
    const liveConditions = (conditions: LogicCondition[] | undefined) => (conditions ?? []).filter((c) => c && fieldIds.has(c.fieldId));

    slides.forEach((slide) => {
        const props = slide?.properties;
        if (!props) return;

        if (Array.isArray(props.jumps)) {
            const jumps = props.jumps.map((j) => ({ ...j, conditions: liveConditions(j.conditions) })).filter((j) => j.conditions.length > 0);
            if (jumps.length) props.jumps = jumps;
            else delete props.jumps;
        }

        props.fields?.forEach((field) => {
            const logic = field?.properties?.logic;
            if (!logic) return;
            const conditions = liveConditions(logic.conditions);
            if (conditions.length) field.properties!.logic = { ...logic, conditions };
            else delete field.properties!.logic;
        });
    });

    return slides;
}
