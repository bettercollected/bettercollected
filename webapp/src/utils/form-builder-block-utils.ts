
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/form-builder';
import { getFieldsFromV2Form } from './form-utils';
import { extractTextfromJSON } from './richTextEditorExtenstion/get-html-from-json';


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
        case FieldTypes.TABULAR_INPUT:
            const tabular_value = response.answers?.[field.id]?.tabular_value;
            if (tabular_value && Array.isArray(tabular_value)) {
                return tabular_value.map((row: string[]) => row.join(', ')).join(' | ');
            }
            return '';
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
        title = field?.value || '';
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
        return [];
    }
}
