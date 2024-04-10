import { JSONContent, generateHTML } from '@tiptap/react';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import {
    Extenstions,
    getPlaceholderValueForTitle
} from '@app/views/molecules/RichTextEditor';

export function getHtmlFromJson(jsonValue: JSONContent | undefined) {
    if (!jsonValue) {
        return null;
    }
    return generateHTML(jsonValue, Extenstions);
}

export function extractTextfromJSON(field: FormField): string {
    const htmlValue =
        getHtmlFromJson(field.title) ??
        getPlaceholderValueForTitle(field.type || FieldTypes.TEXT);
    // .replace(/<[^>]+>/g, ' ')
    return htmlValue.replace(/<\/?[^>]+(>|$)/g, '');
}