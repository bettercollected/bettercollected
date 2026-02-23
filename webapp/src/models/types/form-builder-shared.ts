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
