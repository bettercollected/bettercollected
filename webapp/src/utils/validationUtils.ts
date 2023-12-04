import _ from 'lodash';

import moment from 'moment/moment';

import { formConstant } from '@app/constants/locales/form';
import { AnswerDto, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { FormValidationError } from '@app/store/fill-form/type';
import { ActionType, Comparison, Condition, ConditionalActions, LogicalOperator } from '@app/store/form-builder/types';

/**
 * Validation method to check if the given value is undefined or not.
 * @description - Uses lodash's `isUndefined` method to check the value
 *
 * @param {any} data - Data can be of any type (string, number,...)
 *
 * @returns {boolean} - Returns true if value is undefined, else false
 * @author Bibishan Pandey
 */
export function isUndefined(data: unknown): boolean {
    return _.isUndefined(data);
}

/**
 * Validation method to check if the given value is null or not.
 * @description - Uses lodash's `isNull` method to check the value
 *
 * @param {any} data - Data can be of any type (string, number,...)
 *
 * @returns {boolean} - Returns true if value is null, else false
 * @author Bibishan Pandey
 */
export function isNull(data: unknown): boolean {
    return _.isNull(data);
}

/**
 * Validation method to check if the given value is neither undefined nor null.
 * @description - Uses another validation helper method `isUndefined` and `isNull`.
 *
 * @see isUndefined
 * @see isNull
 *
 * @param {any} data - Data can be of any type (string, number,...)
 *
 * @returns {boolean} - Returns true if value is neither undefined nor null, else false
 * @author Bibishan Pandey
 */
export function isNetherUndefinedNorNull(data: unknown): boolean {
    return !isUndefined(data) && !isNull(data);
}

export const statusProps = (status: string, t: any) => {
    let currentStatus = t('FORM.STATUS_DELETED');
    let cName = 'bg-black-200 !text-black-800 dark:bg-yellow-900 dark:text-yellow-300';
    let dotCName = 'bg-black-800';
    if (status.toLowerCase() === 'pending') {
        currentStatus = t(formConstant.status.pending);
        cName = 'bg-red-200 !text-red-400 dark:bg-red-900 dark:text-red-300';
        dotCName = 'bg-red-400';
    } else if (status.toLowerCase() === 'deleted') {
        currentStatus = t(formConstant.status.expired);
        cName = 'bg-yellow-100 !text-yellow-500';
        dotCName = 'bg-yellow-400';
    }
    return {
        currentStatus,
        cName,
        dotCName
    };
};
export const validateFormFieldAnswer = (field: StandardFormFieldDto, answer: AnswerDto) => {
    const errors: FormValidationError[] = [];

    const { properties, type, validations } = field || {};
    const { text, number, choices } = answer || {};

    if (!properties?.hidden) {
        if (!answer) {
            if (validations?.required) {
                errors.push(FormValidationError.REQUIRED);
            }
        } else {
            if ((type === FormBuilderTagNames.INPUT_SHORT_TEXT || type === FormBuilderTagNames.INPUT_LONG_TEXT) && text) {
                const textLength = text.length;
                if (validations?.minLength && textLength < validations.minLength) {
                    errors.push(FormValidationError.INSUFFICIENT_LENGTH);
                }
                if (validations?.maxLength && textLength > validations.maxLength) {
                    errors.push(FormValidationError.EXCEEDS_MAX_LENGTH);
                }
                if (validations?.regex && text.match(validations.regex)) {
                    errors.push(FormValidationError.REGEX_PATTERN);
                }
            } else if (type === FormBuilderTagNames.INPUT_NUMBER && number !== undefined) {
                if (validations?.minValue && number < validations.minValue) {
                    errors.push(FormValidationError.INSUFFICIENT_VALUE);
                }
                if (validations?.maxValue && number > validations.maxValue) {
                    errors.push(FormValidationError.EXCEEDS_MAX_VALUE);
                }
            } else if ((type === FormBuilderTagNames.INPUT_CHECKBOXES || type === FormBuilderTagNames.INPUT_MULTISELECT) && choices) {
                const choicesLength = choices.values?.length || 0;
                if (validations?.minChoices && choicesLength < validations.minChoices) {
                    errors.push(FormValidationError.INSUFFICIENT_CHOICES);
                }
                if (validations?.maxChoices && choicesLength > validations.maxChoices) {
                    errors.push(FormValidationError.INSUFFICIENT_CHOICES);
                }
            }
        }
    }

    return errors;
};

export const validateFormOpen = (date?: string) => {
    return !date || moment.utc(date).isAfter(moment.utc());
};

export const validateFieldConditions = (answers: Record<string, any>, field: StandardFormFieldDto): boolean => {
    let validity = field?.properties?.logicalOperator === LogicalOperator.AND;
    field?.properties?.conditions.forEach((condition: Condition) => {
        if (field?.properties?.logicalOperator === LogicalOperator.AND) validity = validity && validateCondition(answers, condition);
        else {
            validity = validity || validateCondition(answers, condition);
        }
    });
    return validity;
};

const validateCondition = (answers: Record<string, any>, condition: Condition): boolean => {
    const answer = answers[condition?.field?.id || ''];
    switch (condition?.comparison) {
        case Comparison.IS_EMPTY:
            return !answer;
        case Comparison.IS_NOT_EMPTY:
            return !!answer;
        case Comparison.IS_NOT_EQUAL:
            return !compareEquality(answer, condition);
        case Comparison.IS_EQUAL:
            return compareEquality(answer, condition);
        case Comparison.CONTAINS:
            return compareContains(answer, condition);
        case Comparison.DOES_NOT_CONTAIN:
            return !compareContains(answer, condition);
        case Comparison.LESS_THAN:
            return answer && !compareGreaterThanEqual(answer, condition);
        case Comparison.LESS_THAN_EQUAL:
            return answer && compareLessThanEqual(answer, condition);
        case Comparison.GREATER_THAN:
            return answer && !compareLessThanEqual(answer, condition);
        case Comparison.GREATER_THAN_EQUAL:
            return answer && compareGreaterThanEqual(answer, condition);
        case Comparison?.STARTS_WITH:
            return compareStartsWith(answer, condition);
        case Comparison.ENDS_WITH:
            return compareEndsWith(answer, condition);
        default:
            return false;
    }
};

export const getValueToCompareBasedOnFieldType = (answer: any, fieldType?: FormBuilderTagNames) => {
    switch (fieldType) {
        case FormBuilderTagNames.INPUT_RATING:
        case FormBuilderTagNames.INPUT_NUMBER:
            return answer?.number;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return answer?.text;
        case FormBuilderTagNames.INPUT_LINK:
            return answer?.url;
        case FormBuilderTagNames.INPUT_EMAIL:
            return answer?.email;
        case FormBuilderTagNames.INPUT_DATE:
            return answer?.date;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return answer?.choice?.value;
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            return answer?.choices?.values;
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return answer?.phone_number;
        default:
            return answer?.value;
    }
};

const compareStartsWith = (answer: any, condition: Condition) => {
    const valueToCompare = getValueToCompareBasedOnFieldType(answer, condition.field?.type);
    return valueToCompare?.startsWith(condition?.value);
};

const compareEndsWith = (answer: any, condition: Condition) => {
    const valueToCompare = getValueToCompareBasedOnFieldType(answer, condition.field?.type);
    return valueToCompare?.endsWith(condition?.value);
};
const compareLessThanEqual = (answer: any, condition: Condition): boolean => {
    if (condition.field?.type === FormBuilderTagNames.INPUT_DATE) {
        return moment(answer?.date).isSameOrBefore(moment(condition.value));
    } else {
        return parseInt(answer?.number) <= parseInt(condition.value);
    }
};

const compareGreaterThanEqual = (answer: any, condition: Condition): boolean => {
    if (condition.field?.type === FormBuilderTagNames.INPUT_DATE) {
        return moment(answer?.date).isSameOrAfter(moment(condition.value));
    } else {
        return parseInt(answer?.number) >= parseInt(condition.value);
    }
};

const compareEquality = (answer: any, condition: Condition): boolean => {
    const valueToCompare = getValueToCompareBasedOnFieldType(answer, condition?.field?.type);
    return valueToCompare == condition?.value;
};

const compareContains = (answer: any, condition: Condition): boolean => {
    const includesOption = (option: any) => answer?.choices?.values.includes(option);

    if (condition.comparison === Comparison.CONTAINS) {
        return Array.isArray(condition?.value) && condition.value.every(includesOption);
    }

    return Array.isArray(condition?.value) && condition?.value.some(includesOption);
};

export const validateConditionsAndReturnUpdatedForm = (formToUpdate: StandardFormDto, answers: Record<string, any>, conditionalFields: Array<StandardFormFieldDto>) => {
    conditionalFields?.forEach((conditionalField: StandardFormFieldDto) => {
        if (validateFieldConditions(answers, conditionalField)) {
            conditionalField?.properties?.actions.forEach((action: ConditionalActions) => {
                if (Array.isArray(action?.payload)) {
                    action.payload.forEach((fieldId) => {
                        const fieldIndex = formToUpdate?.fields.findIndex((field) => field.id === fieldId);
                        if (fieldIndex !== -1) {
                            formToUpdate.fields = formToUpdate.fields.map((field, index) => {
                                if (index === fieldIndex) {
                                    switch (action.type) {
                                        case ActionType.SHOW_FIELDS:
                                        case ActionType.HIDE_FIELDS:
                                            return {
                                                ...field,
                                                properties: {
                                                    ...field.properties,
                                                    hidden: action.type === ActionType.HIDE_FIELDS
                                                }
                                            };
                                        case ActionType.REQUIRE_ANSWERS:
                                            return {
                                                ...field,
                                                validations: {
                                                    ...(field?.validations || {}),
                                                    required: true
                                                }
                                            };
                                        default:
                                            return field;
                                    }
                                } else {
                                    return field;
                                }
                            });
                        }
                    });
                }
            });
        }
    });
    return formToUpdate;
};
