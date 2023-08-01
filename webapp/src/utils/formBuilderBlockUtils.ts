import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { v4 } from 'uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { IFormFieldState } from '@app/store/form-builder/types';

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
 */
export function contentEditableClassNames(isPlaceholder: boolean, tag: string = FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
    let className = 'outline-none placeholder-gray-400 ';
    if (isPlaceholder) className += 'text-neutral-200 ';
    else className += 'text-neutral-800 ';

    switch (tag) {
        case FormBuilderTagNames.LAYOUT_HEADER1:
            className += ' text-4xl font-semibold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER2:
            className += ' text-3xl font-semibold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER3:
            className += ' text-2xl font-semibold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER4:
            className += ' text-xl font-semibold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER5:
            className += ' text-lg font-semibold';
            break;
        case FormBuilderTagNames.LAYOUT_LABEL:
            className += ' text-base font-semibold';
            break;
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
            className += ' text-base';
            break;
        default:
            break;
    }

    return className;
}

export function isMultipleChoice(type?: FormBuilderTagNames): boolean {
    if (!type) return false;
    const mulipleChoiceTypes = [FormBuilderTagNames.INPUT_CHECKBOXES, FormBuilderTagNames.INPUT_MULTIPLE_CHOICE, FormBuilderTagNames.INPUT_DROPDOWN, FormBuilderTagNames.INPUT_RANKING];
    return mulipleChoiceTypes.includes(type);
}

export const createNewChoice = () => {
    const id = uuidv4();
    return { id, value: '' };
};

export const createNewField = (position: number): IFormFieldState => {
    return {
        id: v4(),
        type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        isCommandMenuOpen: false,
        position
    };
};
