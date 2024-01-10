import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { v4 } from 'uuid';

import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { IChoiceFieldState, IFormFieldState } from '@app/store/form-builder/types';

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
        if (LabelFormBuilderTagNames.includes(previousField?.type)) {
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
