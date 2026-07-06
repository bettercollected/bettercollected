import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, FieldConditionalLogic, LogicalOperator, LogicCondition } from '@app/models/types/form-builder-shared';

export type { FieldConditionalLogic, LogicAction, LogicCondition } from '@app/models/types/form-builder-shared';

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

/** Are a rule's conditions satisfied given the current answers? */
export function areConditionsMet(logic: FieldConditionalLogic, answers: Record<string, any>): boolean {
    const conditions = logic?.conditions?.filter((c) => c && c.fieldId && c.comparison) ?? [];
    if (conditions.length === 0) return false;
    if (logic.operator === LogicalOperator.OR) {
        return conditions.some((c) => evaluateCondition(answers, c));
    }
    return conditions.every((c) => evaluateCondition(answers, c));
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
