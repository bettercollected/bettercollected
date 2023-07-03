import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

export function extractBlockTypeNames() {}

export function extractFormBuilderTagNames() {}

export function mapFormBuilderTagNames() {}

export function isContentEditableTag(tag: string): boolean {
    const editableTags: Array<string> = [
        FormBuilderTagNames.LAYOUT_HEADER1 as string,
        FormBuilderTagNames.LAYOUT_HEADER2 as string,
        FormBuilderTagNames.LAYOUT_HEADER3 as string,
        FormBuilderTagNames.LAYOUT_HEADER4 as string,
        FormBuilderTagNames.LAYOUT_HEADER5 as string,
        FormBuilderTagNames.LAYOUT_SHORT_TEXT as string,
        FormBuilderTagNames.LAYOUT_LABEL as string
    ];
    return editableTags.includes(tag);
}

/**
 * Return tailwind classNames for the selected layout blocks tag
 * @param isPlaceholder
 * @param tag - tagName
 */
export function contentEditableClassNames(isPlaceholder: boolean, tag: string = FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
    let className = '';
    if (isPlaceholder) className += 'text-neutral-200';
    else className += 'text-neutral-800';

    switch (tag) {
        case FormBuilderTagNames.LAYOUT_HEADER1:
            className += ' text-4xl font-bold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER2:
            className += ' text-3xl font-bold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER3:
            className += ' text-2xl font-bold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER4:
            className += ' text-xl font-bold';
            break;
        case FormBuilderTagNames.LAYOUT_HEADER5:
            className += ' text-lg font-bold';
            break;
        case FormBuilderTagNames.LAYOUT_LABEL:
            className += ' text-base font-bold';
            break;
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
            className += ' text-base';
            break;
        default:
            break;
    }

    return className;
}
