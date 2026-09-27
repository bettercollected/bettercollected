import { FieldTypes } from '@app/models/dtos/form';
import { getComparableAnswerValue, getGroupAnswerItems } from '@app/utils/conditional-logic';

/**
 * Values computed across the items of a repeating group — the building blocks
 * of "calculations" over a group (the form has no calculated-field type yet, so
 * these are exposed through answer piping: `{{group:<groupId>:sum:<fieldId>}}`).
 *
 * Kept free of UI and piping imports so conditional logic, piping and exports
 * can all share it without import cycles.
 */

export type GroupAggregate = 'count' | 'list' | 'sum' | 'avg' | 'min' | 'max';

export const NUMERIC_AGGREGATES: GroupAggregate[] = ['sum', 'avg', 'min', 'max'];

export const GROUP_AGGREGATE_LABELS: Record<GroupAggregate, string> = {
    count: 'number of items',
    list: 'list of',
    sum: 'sum of',
    avg: 'average of',
    min: 'minimum of',
    max: 'maximum of'
};

/** Child question types that hold a number (the only valid aggregate sources). */
export const NUMERIC_FIELD_TYPES: string[] = [FieldTypes.NUMBER, FieldTypes.RATING, FieldTypes.LINEAR_RATING];

/** Numbers answered for one child question across the items (unanswered/NaN skipped). */
export function getGroupNumbers(groupAnswer: any, childId: string, childType: string): number[] {
    return getGroupAnswerItems(groupAnswer)
        .map((item) => getComparableAnswerValue(item?.[childId], childType))
        .filter((value) => value !== undefined && value !== null && value !== '' && !Array.isArray(value))
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value));
}

/** sum / average / minimum / maximum of a numeric child question; undefined when nothing is answered. */
export function aggregateGroupNumbers(groupAnswer: any, childId: string, childType: string, aggregate: GroupAggregate): number | undefined {
    const numbers = getGroupNumbers(groupAnswer, childId, childType);
    if (!numbers.length) return aggregate === 'sum' ? 0 : undefined;
    switch (aggregate) {
        case 'sum':
            return numbers.reduce((a, b) => a + b, 0);
        case 'avg':
            return numbers.reduce((a, b) => a + b, 0) / numbers.length;
        case 'min':
            return Math.min(...numbers);
        case 'max':
            return Math.max(...numbers);
        default:
            return undefined;
    }
}

/** Display a computed number: integers as-is, otherwise at most two decimals. */
export function formatAggregate(value: number | undefined): string | undefined {
    if (value === undefined || !Number.isFinite(value)) return undefined;
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
}

/** "A", "A and B", "A, B and C". */
export function joinList(values: string[]): string | undefined {
    const parts = values.map((v) => String(v).trim()).filter(Boolean);
    if (!parts.length) return undefined;
    if (parts.length === 1) return parts[0];
    return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

/** One child question's answers across the items, as display strings. */
export function getGroupValues(groupAnswer: any, childId: string, childType: string): string[] {
    return getGroupAnswerItems(groupAnswer)
        .map((item) => getComparableAnswerValue(item?.[childId], childType))
        .map((value) => (Array.isArray(value) ? value.join(', ') : value === undefined || value === null ? '' : String(value)))
        .filter((value) => value !== '');
}

/** Resolve an aggregate to display text (count needs no child question). */
export function resolveGroupAggregate(groupAnswer: any, aggregate: GroupAggregate, childId?: string, childType?: string): string | undefined {
    if (aggregate === 'count') return String(getGroupAnswerItems(groupAnswer).length);
    if (!childId) return undefined;
    if (aggregate === 'list') return joinList(getGroupValues(groupAnswer, childId, childType ?? ''));
    return formatAggregate(aggregateGroupNumbers(groupAnswer, childId, childType ?? '', aggregate));
}
