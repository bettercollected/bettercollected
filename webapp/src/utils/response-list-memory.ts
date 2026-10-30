/**
 * Which responses the staff member just saw in the list, so a response's page
 * can offer "previous" and "next" without loading the list again.
 *
 * Only response ids are kept (opaque handles, no answers, no email, no search
 * text), only in this module's memory (gone on reload; never in storage), for
 * one list at a time: a different form, page size or total (another search)
 * starts a new one. Opened in a new tab nothing is known, so there are no
 * previous/next links, which is honest.
 */
export interface ResponseNeighbours {
    previousId?: string;
    nextId?: string;
}

interface Remembered {
    formId: string;
    size: number;
    total: number;
    pages: Map<number, string[]>;
}

let list: Remembered | null = null;

/** Called by the responses table whenever it shows a page of the list. */
export function rememberResponseListPage(formId: string, { page, size, total, ids }: { page: number; size: number; total: number; ids: string[] }) {
    if (!list || list.formId !== formId || list.size !== size || list.total !== total) list = { formId, size, total, pages: new Map() };
    list.pages.set(page, ids);
}

export function forgetResponseList() {
    list = null;
}

/**
 * The previous and next response id around `responseId` in the remembered
 * list. Across a page edge only when the neighbouring page was seen too.
 */
export function rememberedNeighbours(formId: string, responseId: string): ResponseNeighbours {
    if (!list || list.formId !== formId) return {};
    for (const [page, ids] of list.pages) {
        const index = ids.indexOf(responseId);
        if (index < 0) continue;
        const before = list.pages.get(page - 1);
        const after = list.pages.get(page + 1);
        return {
            previousId: index > 0 ? ids[index - 1] : before?.[before.length - 1],
            nextId: index < ids.length - 1 ? ids[index + 1] : after?.[0]
        };
    }
    return {};
}
