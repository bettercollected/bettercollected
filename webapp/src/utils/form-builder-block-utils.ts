
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/form-builder';
import { calculatedAnswerValue, formatCalculatedValue } from '@app/utils/calculated-fields';
import { addressLine } from '@app/utils/address';
import { currencyExportText } from '@app/utils/currency';
import { dateRangeExportText, dateRangeText } from '@app/utils/date-range';
import { calendarDayIn } from '@app/utils/date-utils';
import { answerSignature, signatureExportText } from '@app/utils/signature';
import { sourcedAnswerTexts } from '@app/utils/option-sources';
import { answerTags } from '@app/utils/tags';
import { getFieldsFromV2Form } from './form-utils';
import { getRepeatSettings, isRepeatingGroup } from './repeating-groups';
import { extractTextfromJSON } from './richTextEditorExtenstion/get-html-from-json';


/** Joins the options of a multi-select answer on screen (the responses table, the response page, the respondent's view): "Reading, Cycling". */
export const DISPLAY_LIST_SEPARATOR = ', ';

/** The answer as a screen shows it: like `getAnswerForField`, but a day reads in the app's date style ("5 November 1990") and a date range as two ("3 November 2026 – 7 November 2026"), and a drawn signature as `drawnSignatureText` (the screen's translation of the marker the CSV carries). */
export function getAnswerDisplayText(response: StandardFormResponseDto, field: StandardFormFieldDto, language: 'en' | 'nl' = 'en', drawnSignatureText?: string) {
    // a drawn signature reads as the dashboard's translated marker; the CSV keeps the server's "[drawn signature]" (getAnswerForField)
    if (field.type === FieldTypes.SIGNATURE && drawnSignatureText && answerSignature(response.answers?.[field.id])?.method === 'drawn') return drawnSignatureText;
    if (field.type === FieldTypes.DATE_RANGE) return dateRangeText(response.answers?.[field.id], language);
    if (field.type === FieldTypes.DAY || field.type === FieldTypes.DATE) return calendarDayIn(String(response.answers?.[field.id]?.date ?? ''), language);
    return getAnswerForField(response, field, DISPLAY_LIST_SEPARATOR);
}

/**
 * `listSeparator` joins the selected options of a multi-select answer. The
 * screens pass DISPLAY_LIST_SEPARATOR; the CSV export passes '; '
 * so the options do not split on the comma that separates the columns.
 */
export function getAnswerForField(response: StandardFormResponseDto, field: StandardFormFieldDto, listSeparator?: string) {
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
        case FieldTypes.DAY:
        case FormBuilderTagNames.INPUT_DATE:
            return answer?.date;
        case FieldTypes.TIME:
            return answer?.time;
        case FieldTypes.CURRENCY:
            // "EUR 12.50": the code, a space and the dot-decimal amount, the same in every language and in the CSV
            return currencyExportText(answer?.currency);
        case FieldTypes.DATE_RANGE:
            // "YYYY-MM-DD/YYYY-MM-DD" (an ISO 8601 interval), the same in every language and in the CSV
            return dateRangeExportText(answer);
        case FieldTypes.ADDRESS:
            // one cell, one line: "street number addition, postcode city" and the country code unless NL, the same in every language and in the CSV
            return addressLine(answer?.address);
        case FieldTypes.TAGS:
            // one cell, "; " between the tags (never the list separator of the choice questions)
            return (answerTags(answer) ?? []).join(listSeparator ?? '; ');
        case FieldTypes.YES_NO:
            return answer?.boolean === true ? 'Yes' : answer?.boolean === false ? 'No' : '';

        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN:
            return getChoicesValue(field, answer, listSeparator ?? ',');

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
                return choices?.map((choice: any) => choice.value)?.join(listSeparator ?? ', ');
            }
            const choices = field?.properties?.choices?.filter((choice: any) => answer?.choices?.values?.includes(choice.id));
            return choices?.map((choice: any) => choice.value)?.join(listSeparator ?? ', ');
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
            return answer?.choices?.values?.map((choice: any) => choice?.value)?.join(listSeparator ?? ', ');
        case FormBuilderTagNames.INPUT_FILE_UPLOAD:
        case FieldTypes.FILE_UPLOAD:
            return answer?.file_metadata?.name;
        case FieldTypes.SIGNATURE:
            // the typed name, or a marker for a drawn one: never the image or a link
            return signatureExportText(answer);
        case FieldTypes.CALCULATED: {
            // The value the server computed and stored, shown with the
            // field's format (currency, percent, decimals). Exports use
            // calculatedExportValue: the raw number.
            const value = calculatedAnswerValue(answer);
            if (value === null) return '';
            if (typeof value === 'boolean') return value ? 'Yes' : 'No';
            return formatCalculatedValue(value, field.properties?.format, 'en');
        }
        case FieldTypes.GROUP: {
            // Repeating group: a one-cell summary ("Applicant × 2"); the
            // per-item answers are shown by the submission view and exports.
            if (!isRepeatingGroup(field)) return '';
            const count = Array.isArray(answer?.items) ? answer.items.length : 0;
            return count ? `${getRepeatSettings(field).itemLabel} × ${count}` : '';
        }
        default:
            return '';
    }
}

function getChoicesValue(field: StandardFormFieldDto, answer: any, separator: string) {
    // options from a list or another form's answers are not in the form: the text stored with the answer, never an id
    if (field.properties?.optionSource) return sourcedAnswerTexts(answer).join(separator);
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
        return [...choicesValue, otherValue]?.join(separator);
    }
    return choicesValue?.join(separator);
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

/**
 * Columns for a responses table whose rows may come from different form
 * versions: the given form's fields first, then any field that only exists in
 * another version, so a response's answers always have a column. Answers are
 * keyed by field id, so a question that was re-created gets its own column.
 */
export function mergeFieldsAcrossVersions(base: StandardFormFieldDto[], others: StandardFormFieldDto[][]): StandardFormFieldDto[] {
    const seen = new Set(base.map((field) => field.id));
    const merged = [...base];
    for (const fields of others) {
        for (const field of fields) {
            if (field?.id && !seen.has(field.id)) {
                seen.add(field.id);
                merged.push(field);
            }
        }
    }
    return merged;
}
