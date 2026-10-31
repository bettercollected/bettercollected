/**
 * Which responses the staff member just saw in a form's responses list, so a
 * response's page can offer "previous" and "next" without loading the list
 * again, and the list can open again on the page and search it was left on.
 *
 * Kept only in this module's memory (gone on reload; never in storage): the
 * response ids of the pages seen (opaque handles, no answers), the page last
 * shown, the list's own URL parameters (filters, sort, page: nothing secret)
 * and the search typed (staff's own words, which may be a responder's email:
 * that is why it never goes into a URL). One list at a time, named by
 * workspace, form, search and view (filters, sort and size): an imported form
 * can exist in two workspaces with the same form id, and two searches with
 * the same total are different lists. Any change of these, of the page size
 * or of the total starts a new one. Opened in a new tab nothing is known, so there are no
 * previous/next links, which is honest.
 */
export interface ResponseListKey {
    workspaceId: string;
    formId: string;
    searchText: string;
    /** The filters, sort and size of the list (utils/response-list-state.ts `responseListView`). */
    view?: string;
}

export interface ResponseNeighbours {
    previousId?: string;
    nextId?: string;
    /** 1-based place of the response in the whole list, when known. */
    position?: number;
    total?: number;
}

interface Remembered extends ResponseListKey {
    /** The page of the list last shown. */
    page: number;
    /** The list's URL parameters when it was last shown (no search text). */
    query?: string;
    size?: number;
    total?: number;
    pages: Map<number, string[]>;
}

let list: Remembered | null = null;

const sameList = (a: ResponseListKey, b: ResponseListKey) => a.workspaceId === b.workspaceId && a.formId === b.formId && a.searchText === b.searchText && (a.view ?? '') === (b.view ?? '');

/** Called by the responses list whenever its page or search changes. */
export function rememberResponseListView(key: ResponseListKey, page: number, query?: string) {
    if (!key.workspaceId || !key.formId) return;
    if (!list || !sameList(list, key)) list = { ...key, page, query, pages: new Map() };
    else {
        list.page = page;
        list.query = query;
    }
}

/** Called by the responses table whenever it shows a page of the list. */
export function rememberResponseListPage(key: ResponseListKey, { page, size, total, ids }: { page: number; size: number; total?: number; ids: string[] }) {
    if (!key.workspaceId || !key.formId) return;
    const changed = !list || !sameList(list, key) || (list.size !== undefined && list.size !== size) || (list.total !== undefined && list.total !== total);
    if (changed) list = { ...key, page, size, total, pages: new Map() };
    const current = list as Remembered;
    current.size = size;
    current.total = total;
    current.page = page;
    current.pages.set(page, ids);
}

/** Forget the list: on logout (the search may be a responder's email, and the next person must not get it back). */
export function forgetResponseList() {
    list = null;
}

/** Called when a workspace opens: a list remembered in another workspace is forgotten. */
export function forgetResponseListOutside(workspaceId: string) {
    if (list && list.workspaceId !== workspaceId) list = null;
}

/** The page, URL parameters and search the form's responses list was left on, to open it there again. */
export function rememberedListView(workspaceId: string | undefined, formId: string | undefined): { page: number; searchText: string; query?: string } | null {
    if (!list || !workspaceId || !formId || list.workspaceId !== workspaceId || list.formId !== formId) return null;
    return { page: list.page, searchText: list.searchText, query: list.query };
}

/**
 * The previous and next response id around `responseId` in the remembered
 * list. Across a page edge only when the neighbouring page was seen too.
 */
export function rememberedNeighbours(workspaceId: string, formId: string, responseId: string): ResponseNeighbours {
    if (!list || list.workspaceId !== workspaceId || list.formId !== formId) return {};
    for (const [page, ids] of list.pages) {
        const index = ids.indexOf(responseId);
        if (index < 0) continue;
        const before = list.pages.get(page - 1);
        const after = list.pages.get(page + 1);
        const neighbours: ResponseNeighbours = {
            previousId: index > 0 ? ids[index - 1] : before?.[before.length - 1],
            nextId: index < ids.length - 1 ? ids[index + 1] : after?.[0]
        };
        if (list.size && list.total) {
            neighbours.position = (page - 1) * list.size + index + 1;
            neighbours.total = list.total;
        }
        return neighbours;
    }
    return {};
}
