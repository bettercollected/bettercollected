import { JSONContent, generateHTML } from '@tiptap/react';

import { FieldTypes, FormField, StandardFormFieldDto } from '@app/models/dtos/form';
import { Extenstions, getPlaceholderValueForTitle } from '@app/views/molecules/RichTextEditor';

export function getHtmlFromJson(value: JSONContent | string | undefined) {
    if (!value) {
        return null;
    }
    if (typeof value === 'string') {
        return `<p>${value}</p>`;
    }
    return generateHTML(value, Extenstions);
}

export function extractTextfromJSON(field: FormField | StandardFormFieldDto): string {
    const htmlValue = getHtmlFromJson(field.title) ?? getPlaceholderValueForTitle(field.type || FieldTypes.TEXT);
    // .replace(/<[^>]+>/g, ' ')
    return htmlValue.replace(/<\/?[^>]+(>|$)/g, '');
}
