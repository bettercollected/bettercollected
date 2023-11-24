import { ActionCreatorWithPayload } from '@reduxjs/toolkit';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

import { AppDispatch } from '../store';

export interface IBuilderMenuState {
    spotlightField?: { isOpen: boolean; afterFieldUuid: string };
    commands?: { isOpen: boolean; atFieldUuid: string; position: 'up' | 'down' };
    fieldSettings?: { isOpen: boolean; atFieldUuid: string };
    pipingFields?: {
        isOpen: boolean;
        atFieldUuid: string;
        position: 'up' | 'down';
        atChar?: number;
        pos: { top: number; left: number };
    };
    pipingFieldSettings?: {
        isOpen: boolean;
        atFieldId: string;
        mentionedFieldId: string;
        pos: { top: number; left: number };
    };
}

export interface IChoiceFieldState {
    id: string;
    value: string;
    position: number;
}

export interface IBuilderPipingState {}

export interface IBuilderStateVersion {
    timestamp: Date | string | number;
    fields: Record<string, IFormFieldState>;
}

export interface IFormBuilderSettingsState {
    responseDataOwnerField?: string;
}

export enum LogicalOperator {
    AND = 'and',
    OR = 'or'
}

export interface IBuilderState {
    id?: string;
    title: string;
    description: string;
    menus?: IBuilderMenuState;
    piping?: IBuilderPipingState;
    logo?: string;
    coverImage?: string;
    fields: Record<string, IFormFieldState>;
    versions?: Array<IBuilderStateVersion>;
    currentVersionIndex?: number;
    settings?: IFormBuilderSettingsState;
    isFormDirty?: boolean;
    activeFieldIndex: number;
    activeFieldId: string;
    isTyping?: boolean;
    activeChoiceId: string;
    activeChoiceIndex: number;
    buttonText?: string;
}

export interface IBuilderStateProps {
    builderState: IBuilderState;
    setBuilderState: ActionCreatorWithPayload<Partial<IBuilderState>, 'builder/setBuilderState'>;
    dispatch: AppDispatch;
}

export enum ActionType {
    JUMP_TO_PAGE = 'jump_to_page',
    CALCULATE = 'calculate',
    REQUIRE_ANSWERS = 'require_answer',
    SHOW_FIELDS = 'show_fields',
    HIDE_FIELDS = 'hide_fields'
}

export interface ConditionalActions {
    id: string;
    position: number;
    type?: ActionType;
    payload?: string[] | string;
}

export interface IFormFieldProperties {
    steps?: number;
    placeholder?: string;
    hidden?: boolean;
    allowMultipleSelection?: boolean;
    choices?: Record<string, IChoiceFieldState>;
    activeChoiceId?: string;
    activeChoiceIndex?: number;
    conditions?: {
        [conditionId: string]: Condition;
    };
    logicalOperator?: LogicalOperator;
    actions?: {
        [actionId: string]: ConditionalActions;
    };
    mentions?: Record<string, string>;
}

export enum Comparison {
    CONTAINS = 'contains',
    DOES_NOT_CONTAIN = 'does_not_contain',
    IS_EQUAL = 'is_equal',
    IS_NOT_EQUAL = 'is_not_equal',
    STARTS_WITH = 'starts_with',
    ENDS_WITH = 'ends_with',
    IS_EMPTY = 'is_empty',
    IS_NOT_EMPTY = 'is_not_empty',
    GREATER_THAN = 'greater_than',
    LESS_THAN = 'less_than',
    GREATER_THAN_EQUAL = 'greater_than_equal',
    LESS_THAN_EQUAL = 'less_than_equal'
}

export enum ConditionalType {
    SINGLE = 'single',
    NESTED = 'nested'
}

export enum FieldType {
    SINGLE = 'single',
    MATRIX = 'matrix'
}

export interface Condition {
    id: string;
    position: number;
    type?: ConditionalType;
    comparison?: Comparison;
    field?: {
        id: string;
        type?: FormBuilderTagNames;
    };
    conditions?: Condition[];
    logicalOperator?: LogicalOperator;
    fieldType?: FieldType;
    value?: any;
}

export interface IFormFieldValidation {
    required?: boolean;
    maxLength?: number;
    minLength?: number;
    maxValue?: number;
    minValue?: number;
    maxChoices?: number;
    minChoices?: number;
    regex?: string;
}

export interface IFormFieldState {
    id: string;
    type: FormBuilderTagNames;
    value?: string;
    groupUuid?: string;
    hasPlaceholder?: boolean;
    isFocused?: boolean;
    isFieldActionMenuOpen?: boolean;
    isCommandMenuOpen?: boolean;
    properties?: IFormFieldProperties;
    cssProperties?: Record<string, string | number>;
    validations?: IFormFieldValidation;
    position: number;
    replace?: boolean;
}

// Builder title and description DTO and Array
export interface IBuilderTitleAndDescriptionObj {
    id: string;
    tagName: string;
    type: FormBuilderTagNames;
    key: 'title' | 'description';
    position: number;
    placeholder: string;
    className: string;
}
