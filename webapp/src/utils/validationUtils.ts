import _ from 'lodash';

import moment from 'moment/moment';

import { formConstant } from '@app/constants/locales/form';
import { AnswerDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { FormValidationError } from '@app/store/fill-form/type';
import { Comparison, Condition, LogicalOperator } from '@app/store/form-builder/types';

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
    const errors: Array<FormValidationError> = [];
    if (!field?.properties?.hidden) {
        if (answer) {
            if (field?.type === FormBuilderTagNames.INPUT_SHORT_TEXT || field?.type === FormBuilderTagNames.INPUT_LONG_TEXT) {
                if (field?.validations?.minLength && (answer?.text || '').length < field?.validations?.minLength) {
                    errors.push(FormValidationError.INSUFFICIENT_LENGTH);
                }
                if (field?.validations?.maxLength && (answer?.text || '').length > field?.validations?.maxLength) {
                    errors.push(FormValidationError.EXCEEDS_MAX_LENGTH);
                }
                if (field?.validations?.regex && answer?.text?.match(field?.validations?.regex || '')) {
                    errors.push(FormValidationError.REGEX_PATTERN);
                }
            }
            if (field?.type === FormBuilderTagNames.INPUT_NUMBER) {
                if (field?.validations?.minValue && (answer?.number || 0) < field?.validations?.minValue) {
                    errors.push(FormValidationError.INSUFFICIENT_VALUE);
                }
                if (field?.validations?.maxValue && (answer?.number || 0) > field?.validations?.maxValue) {
                    errors.push(FormValidationError.EXCEEDS_MAX_VALUE);
                }
            }

            if (field?.type === FormBuilderTagNames.INPUT_CHECKBOXES || field?.type === FormBuilderTagNames.INPUT_MULTISELECT) {
                if (field?.validations?.minChoices && (answer?.choices?.values?.length || 0) < field?.validations?.minChoices) {
                    errors.push(FormValidationError.INSUFFICIENT_CHOICES);
                }
                if (field?.validations?.maxChoices && (answer?.choices?.values?.length || 0) > field?.validations?.maxChoices) {
                    errors.push(FormValidationError.INSUFFICIENT_CHOICES);
                }
            }
        } else {
            if (field?.validations?.required) {
                errors.push(FormValidationError.REQUIRED);
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
    const fieldId: string = condition?.field?.id || '';
    switch (condition?.comparison) {
        case Comparison.IS_EMPTY:
            return !answers[fieldId];
        case Comparison.IS_NOT_EMPTY:
            return !!answers[fieldId];
        case Comparison.IS_NOT_EQUAL:
            return !compareEquality(answers[fieldId], condition);
        case Comparison.IS_EQUAL:
            return compareEquality(answers[fieldId], condition);
        default:
            return false;
    }
};

const compareEquality = (answer: any, condition: Condition): boolean => {
    switch (condition.field?.type) {
        case FormBuilderTagNames.INPUT_EMAIL:
        case FormBuilderTagNames.INPUT_NUMBER:
        case FormBuilderTagNames.INPUT_LONG_TEXT:
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_DATE:
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
        case FormBuilderTagNames.INPUT_LINK:
        case FormBuilderTagNames.INPUT_RATING:
            return answer?.value === condition?.value;

        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return answer?.choice?.value === condition?.value;
        default:
            return false;
    }
};
