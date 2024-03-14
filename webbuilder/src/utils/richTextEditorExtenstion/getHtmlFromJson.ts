import { JSONContent, generateHTML } from '@tiptap/react';

import { Extenstions } from '@app/views/molecules/RichTextEditor';

export function getHtmlFromJson(jsonValue: JSONContent | undefined) {
    if (!jsonValue) {
        return null;
    }
    // if (typeof jsonValue === 'string') {
    // return generateHTML(JSON.parse(jsonValue), Extenstions);
    // }
    return generateHTML(jsonValue, Extenstions);
}
