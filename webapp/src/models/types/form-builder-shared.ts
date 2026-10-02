export enum LogicalOperator {
    AND = 'AND',
    OR = 'OR'
}

export enum Comparison {
    IS_EMPTY = 'IS_EMPTY',
    IS_NOT_EMPTY = 'IS_NOT_EMPTY',
    IS_EQUAL = 'IS_EQUAL',
    IS_NOT_EQUAL = 'IS_NOT_EQUAL',
    CONTAINS = 'CONTAINS',
    DOES_NOT_CONTAIN = 'DOES_NOT_CONTAIN',
    LESS_THAN = 'LESS_THAN',
    LESS_THAN_EQUAL = 'LESS_THAN_EQUAL',
    GREATER_THAN = 'GREATER_THAN',
    GREATER_THAN_EQUAL = 'GREATER_THAN_EQUAL',
    STARTS_WITH = 'STARTS_WITH',
    ENDS_WITH = 'ENDS_WITH'
}

export enum ActionType {
    SHOW_FIELDS = 'SHOW_FIELDS',
    HIDE_FIELDS = 'HIDE_FIELDS',
    REQUIRE_ANSWERS = 'REQUIRE_ANSWERS'
}

export enum FieldType {
    MATRIX = 'matrix'
}

export interface Condition {
    field?: {
        id: string;
        type: string | any;
    };
    comparison: Comparison | any;
    value: any;
}

export interface ConditionalActions {
    type: ActionType | any;
    payload: string[];
}

/**
 * v2 conditional-visibility rule stored on a field at `properties.logic`.
 * See `utils/conditional-logic.ts` for evaluation. Kept here (a dependency-free
 * types module) so `dtos/form.ts` can reference it without a circular import.
 */
export type LogicAction = 'SHOW' | 'HIDE';

export interface LogicCondition {
    /** id of the earlier field whose answer drives this condition */
    fieldId: string;
    /** type of that source field — tells us which answer slot to compare */
    fieldType: string;
    comparison: Comparison;
    value: any;
    /**
     * Only when `fieldId` is a repeating group — conditions on the group as a
     * whole (there is deliberately no condition on a specific item):
     *  - `COUNT`: the number of items compared with `value`;
     *  - `ANY` / `ALL`: `comparison`/`value` applied to `childFieldId` in each item.
     */
    groupMode?: GroupConditionMode;
    childFieldId?: string;
    childFieldType?: string;
}

export type GroupConditionMode = 'COUNT' | 'ANY' | 'ALL';

/**
 * Makes a `group` field repeatable (stored at `properties.repeat`): its child
 * questions are answered once per item. See utils/repeating-groups.ts.
 */
export interface RepeatSettings {
    minItems?: number;
    maxItems?: number;
    /** Names one item ("Applicant"); labels "Add another Applicant". */
    itemLabel?: string;
    /** Optional item header template; may pipe a sibling: `{{field:<child id>}}`. */
    itemTitle?: string;
    /** Export shape override; default columns when maxItems <= 5, else rows. */
    exportLayout?: 'columns' | 'rows';
}

export type DateRuleComparison = 'before' | 'after' | 'on_or_before' | 'on_or_after';
export type DateRuleTarget = 'date' | 'today' | 'field';

/**
 * A constraint on a date question's answer (stored at `properties.dateRules`):
 * the chosen date must be `comparison` a fixed `date` (YYYY-MM-DD), today, or
 * the answer of another date question (`fieldId`). See utils/date-rules.ts.
 */
export interface DateRule {
    comparison: DateRuleComparison;
    target: DateRuleTarget;
    /** YYYY-MM-DD, when `target` is `date`. */
    date?: string;
    /** Another date question, when `target` is `field`. */
    fieldId?: string;
}

export interface FieldConditionalLogic {
    action: LogicAction;
    operator: LogicalOperator;
    conditions: LogicCondition[];
}

/** Sentinel jump target meaning "end the form / go to the thank-you page". */
export const JUMP_TARGET_SUBMIT = '__SUBMIT__';

/** Canvas coordinates of a page node in the Flow view. Cosmetic only. */
export interface NodePosition {
    x: number;
    y: number;
}

/**
 * A page-jump / branching rule stored on a slide at `properties.jumps`.
 * Evaluated in order when the responder leaves the page; the first rule whose
 * conditions match wins and sends them to `target` (a slide id, or
 * JUMP_TARGET_SUBMIT). No match → linear next page.
 */
export interface PageJump {
    operator: LogicalOperator;
    conditions: LogicCondition[];
    /** target slide id, or JUMP_TARGET_SUBMIT */
    target: string;
}

export interface IFormFieldValidation {
    required?: boolean;
    minLength?: number;
    maxLength?: number;
    minValue?: number;
    maxValue?: number;
    minChoices?: number;
    maxChoices?: number;
    regex?: string;
}

export interface IChoiceFieldState {
    id: string;
    value: string;
    position: number;
}

export interface IFormFieldState {
    id: string;
    type: string | any;
    isCommandMenuOpen: boolean;
    position: number;
}
