import { generateHTML } from '@tiptap/react';

import { Extenstions } from '@app/views/molecules/RichTextEditor';

export function getHtmlFromJson(jsonString: string) {
    if (!jsonString) {
        return null;
    }
    return generateHTML(JSON.parse(jsonString), Extenstions);
}
