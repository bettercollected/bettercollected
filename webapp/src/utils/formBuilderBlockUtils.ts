import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { v4 } from 'uuid';

import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { IChoiceFieldState, IFormFieldState } from '@app/store/form-builder/types';
import { getFieldsFromV2Form } from './formUtils';
import { extractTextfromJSON } from './richTextEditorExtenstion/getHtmlFromJson';

export function extractBlockTypeNames() {}

export function extractFormBuilderTagNames() {}

export function mapFormBuilderTagNames() {}

export function isContentEditableTag(tag: string): boolean {
    const editableTags: Array<string> = [FormBuilderTagNames.LAYOUT_SHORT_TEXT as string];
    return editableTags.includes(tag);
}

/**
 * Return tailwind classNames for the selected layout blocks tag
 * @param isPlaceholder
 * @param tag - tagName
 *@param enabled
 */
export function contentEditableClassNames(isPlaceholder: boolean, tag: string = FormBuilderTagNames.LAYOUT_SHORT_TEXT, enabled?: boolean) {
    let className = ' outline-none placeholder-gray-400 ';
    if (isPlaceholder) className += 'text-neutral-200 ';
    else if (!enabled) className += 'text-black-600 ';
    else className += 'text-black-900 ';

    switch (tag) {
        case FormBuilderTagNames.LAYOUT_HEADER1:
            className += ' text-[32px] font-bold text-black-800';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER2:
            className += ' text-[24px] font-semibold text-black-800';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER3:
            className += ' text-[20px] font-semibold text-black-800';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER4:
            className += ' text-[16px] text-black-800 font-medium';
            break;
        case FormBuilderTagNames.LAYOUT_LABEL:
            className += ' text-[16px] font-medium leading-normal text-black-800';
            break;
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
            className += ' text-[16px] font-medium leading-normal text-black-800';
            break;
        default:
            break;
    }

    return className;
}

export function isMultipleChoice(type?: FormBuilderTagNames): boolean {
    if (!type) return false;
    const multipleChoiceTypes = [FormBuilderTagNames.INPUT_CHECKBOXES, FormBuilderTagNames.INPUT_MULTIPLE_CHOICE, FormBuilderTagNames.INPUT_DROPDOWN, FormBuilderTagNames.INPUT_RANKING, FormBuilderTagNames.INPUT_MULTISELECT];
    return multipleChoiceTypes.includes(type);
}

export const createNewChoice = (position: number): IChoiceFieldState => {
    const id = uuidv4();
    return { id, value: '', position };
};

export const createNewField = (position: number, type?: FormBuilderTagNames): IFormFieldState => {
    return {
        id: v4(),
        type: type ?? FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        isCommandMenuOpen: false,
        position
    };
};

export const createNewAction = (actionId: string, position: number) => {
    return {
        position: position,
        id: actionId,
        payload: []
    };
};

export function getPreviousField(fields: Array<IFormFieldState>, currentField: IFormFieldState) {
    return fields[currentField.position - 1] || undefined;
}

export function getNextField(fields: Array<IFormFieldState>, currentField: IFormFieldState) {
    return fields[currentField.position + 1] || undefined;
}

export function getDisplayNameForField(fields: Array<IFormFieldState>, fieldId: string) {
    const currentField = fields.find((field: any) => field.id === fieldId);
    if (currentField) {
        const previousField = getPreviousField(fields, currentField);
        let text = currentField.properties?.placeholder;
        if (LabelFormBuilderTagNames.includes(previousField?.type) || previousField?.type === FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
            text = previousField?.value || currentField?.type;
        }
        return text;
    }
    return '';
}

export function convertPlaceholderToDisplayValue(fields: Array<IFormFieldState>, inputString?: string): string {
    const placeholderRegex = /{{\s*([0-9a-fA-F-]+)\s*}}/g;

    // Use replace with a callback function to replace the placeholder
    let displayString = inputString?.replace(placeholderRegex, (match, fieldId) => {
        if (fields?.find((field: IFormFieldState) => field.id === fieldId)) return `@${getDisplayNameForField(fields, fieldId)}`;
        return '';
    });

    if (displayString?.match(placeholderRegex)) {
        displayString = convertPlaceholderToDisplayValue(fields, displayString);
    }
    return displayString || '';
}

export function getAnswerForField(response: StandardFormResponseDto, field: StandardFormFieldDto) {
    const answer = response.answers[field.id];

    switch (field.type) {
        case FormBuilderTagNames.INPUT_RATING:
        case FormBuilderTagNames.INPUT_NUMBER:
        case FieldTypes.LINEAR_RATING:
        case FieldTypes.RATING:
        case FieldTypes.NUMBER:
            return answer?.number;
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LONG_TEXT:
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return answer?.text;
        case FieldTypes.LINK:
        case FormBuilderTagNames.INPUT_LINK:
            return answer?.url;
        case FieldTypes.EMAIL:
        case FormBuilderTagNames.INPUT_EMAIL:
            return answer?.email;
        case FieldTypes.DATE:
        case FormBuilderTagNames.INPUT_DATE:
            return answer?.date;
        case FieldTypes.YES_NO:
            return answer?.boolean === true ? 'Yes' : answer?.boolean === false ? 'No' : '';

        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN:
            return getChoicesValue(field, answer);

        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
        case FormBuilderTagNames.INPUT_DROPDOWN:
            const compareValue = !answer?.choice?.value?.match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$');
            if (compareValue) {
                return field?.properties?.choices?.find((choice: any) => choice.value === answer?.choice?.value)?.value;
            }
            return field?.properties?.choices?.find((choice: any) => choice.id === answer?.choice?.value)?.value;
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            const choicesAnswers = answer?.choices?.values;
            const compareIds = Array.isArray(choicesAnswers) && choicesAnswers.length > 0 && choicesAnswers?.every((choice: any) => choice.match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'));
            if (!compareIds) {
                const choices = field?.properties?.choices?.filter((choice: any) => answer?.choices?.values?.includes(choice.value));
                return choices?.map((choice: any) => choice.value)?.join(', ');
            }
            const choices = field?.properties?.choices?.filter((choice: any) => answer?.choices?.values?.includes(choice.id));
            return choices?.map((choice: any) => choice.value)?.join(', ');
        case FieldTypes.PHONE_NUMBER:
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return answer?.phone_number;
        case FormBuilderTagNames.INPUT_RANKING:
            return answer?.choices?.values?.map((choice: any) => choice?.value)?.join(', ');
        case FormBuilderTagNames.INPUT_FILE_UPLOAD:
        case FieldTypes.FILE_UPLOAD:
            return answer?.file_metadata?.name;
        default:
            return '';
    }
}

function getChoicesValue(field: StandardFormFieldDto, answer: any) {
    const choices = field.properties?.allowMultipleSelection
        ? field?.properties?.choices?.filter((choice: any) => answer?.choices?.values?.includes(choice.id))
        : field?.properties?.choices?.filter((choice: any) => answer?.choice?.value?.includes(choice.id));
    const otherValue = getMultipleChoiceOtherValue(answer, field.properties?.allowMultipleSelection);
    const choicesValue = choices?.map((choice: any) => {
        if (choice.value) {
            return choice.value;
        } else {
            const choiceIndex = field?.properties?.choices?.findIndex((item: any) => item.id === choice.id);
            return choiceIndex == -1 ? '' : 'Item ' + (+choiceIndex! + 1);
        }
    });
    if (otherValue && choicesValue) {
        return [...choicesValue, otherValue]?.join(',');
    }
    return choicesValue?.join(',');
}

function getMultipleChoiceOtherValue(answer: any, multipleSelection: boolean = false): string {
    if (multipleSelection) {
        return answer?.choices?.other ? answer.choices?.other : '';
    } else {
        return answer?.choice?.other ? answer.choice?.other : '';
    }
}

export function getTitleForHeader(field: StandardFormFieldDto, form: StandardFormDto) {
    let title: string = '';
    if (form.builderVersion === 'v2') {
        title = extractTextfromJSON(field);
    } else if (form.builderVersion !== 'v2' && form.settings?.provider === 'google') {
        // @ts-ignore
        title = field.title || '';
    } else {
        title = convertPlaceholderToDisplayValue(
            form?.fields.map((field: any, index: number) => {
                return {
                    ...field,
                    position: index
                };
            }) ?? [],
            field?.value || ''
        );
    }
    return title;
}

export function getFormFields(form: StandardFormDto) {
    if (form.builderVersion === 'v2') {
        return getFieldsFromV2Form(form);
    } else {
        return getFilteredInputFields(form);
    }
}

function getFilteredInputFields(form: StandardFormDto) {
    if (form?.settings?.provider === 'google') {
        return form?.fields.filter((field) => field.type !== null);
    } else {
        return getFilteredV1InputFields(form);
    }
}

function getFilteredV1InputFields(form: StandardFormDto) {
    const filteredFields: Array<any> = [];
    form?.fields.forEach((field, index) => {
        if (field.type.includes('input_')) {
            const x: any = {
                fieldId: field.id,
                id: field.id
            };
            const previousField = form?.fields[index - 1] || undefined;
            let text = field?.properties?.placeholder;
            if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                text = previousField?.value;
            }
            x.value = text;
            x.type = field.type;
            x.properties = field?.properties;
            filteredFields.push(x);
        }
    });
    return filteredFields;
}
