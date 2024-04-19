import { generateHTML, JSONContent } from '@tiptap/react';

import { FieldTypes, StandardFormFieldDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { Extenstions, getPlaceholderValueForTitle } from '@app/views/molecules/RichTextEditor';

export function getHtmlFromJson(value: JSONContent | string | undefined) {
    if (!value) {
        return null;
    }
    if (typeof value === 'string') {
        return `<p><strong>${value}</strong></p>`;
    }
    return generateHTML(value, Extenstions);
}

export function extractTextfromJSON(field: StandardFormFieldDto | StandardFormFieldDto): string {
    const htmlValue = getHtmlFromJson(field.title) ?? getPlaceholderValueForTitle(field.type || FieldTypes.TEXT);
    // .replace(/<[^>]+>/g, ' ')
    return htmlValue.replace(/<\/?[^>]+(>|$)/g, '');
}
