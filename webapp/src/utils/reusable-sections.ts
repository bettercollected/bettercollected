/**
 * Reusable sections in the builder: finding a copy of a library section in a page and what replacing it
 * takes (the pure part; the calls are `lib/hooks/use-reusable-sections.ts`). A copy is the questions that
 * carry the same `properties.library.instance`; see docs/reusable-sections.md.
 */
import type { LayoutContainer, LibraryOrigin, StandardFormFieldDto } from '@app/models/dtos/form';
import { containersOf, membersOf, pageFieldsOf } from '@app/utils/layout-containers';

type Page = { id: string; properties?: { fields?: StandardFormFieldDto[]; containers?: LayoutContainer[] } } | undefined | null;

export const libraryOf = (field: StandardFormFieldDto | undefined | null): LibraryOrigin | undefined => field?.properties?.library ?? undefined;

/** The page's own questions that belong to this insert, in page order. */
export const instanceFields = (page: Page, instance: string): StandardFormFieldDto[] => pageFieldsOf(page as any).filter((field) => libraryOf(field)?.instance === instance);

/** The containers that sit wholly inside the copy (a container that also holds other questions is the creator's). */
export function instanceContainers(page: Page, ids: Set<string>): LayoutContainer[] {
    return containersOf(page as any).filter((container) => {
        const members = membersOf(container);
        return members.length > 0 && members.every((id) => ids.has(id));
    });
}

export interface ReplaceTarget {
    replaceIds: string[];
    replaceContainerIds: string[];
    /** Where the new questions go among the page's others once the copy is taken out. */
    index: number;
}

/** What replacing a copy takes: its questions and containers, and the place it was at. */
export function replaceTarget(page: Page, instance: string): ReplaceTarget | null {
    const mine = instanceFields(page, instance);
    if (!mine.length) return null;
    const ids = new Set(mine.map((field) => field.id));
    const all = pageFieldsOf(page as any);
    const first = all.findIndex((field) => ids.has(field.id));
    return {
        replaceIds: mine.map((field) => field.id),
        replaceContainerIds: instanceContainers(page, ids).map((container) => container.id),
        index: all.slice(0, first).filter((field) => !ids.has(field.id)).length
    };
}

/** The translation key of the sentence for a warning the server gave when a section was saved. */
export const warningKey = (code: string): string => `SECTIONS_LIB.WARNING.${String(code).toUpperCase()}`;

/** The translation key of what differs in a changed question. */
export const whatKey = (what: string): string => `SECTIONS_LIB.WHAT.${String(what).toUpperCase()}`;

/** The ops that put a fragment on a page (`splice_fields`; one undo step). */
export function spliceOps(pageId: string, fragment: { fields: unknown[]; containers: unknown[] }, target: Partial<ReplaceTarget> & { index?: number }) {
    return [
        {
            op: 'splice_fields',
            pageId,
            ...(target.index != null ? { index: target.index } : {}),
            fields: fragment.fields,
            ...(fragment.containers.length ? { containers: fragment.containers } : {}),
            ...(target.replaceIds?.length ? { replaceIds: target.replaceIds } : {}),
            ...(target.replaceContainerIds?.length ? { replaceContainerIds: target.replaceContainerIds } : {})
        }
    ];
}

/** The server's refusal as a sentence for a toast: its `message`, else the fallback. */
export const refusalText = (error: any, fallback: string): string => (typeof error?.data?.message === 'string' ? error.data.message : fallback);

/** A question's title as plain text (a rich title's text nodes joined). */
export function plainTitle(field: { title?: unknown } | undefined | null): string {
    const title = field?.title;
    if (typeof title === 'string') return title.trim();
    const parts: string[] = [];
    const pending: any[] = title && typeof title === 'object' ? [title] : [];
    while (pending.length && parts.length < 400) {
        const node = pending.shift();
        if (typeof node?.text === 'string') parts.push(node.text);
        if (Array.isArray(node?.content)) pending.unshift(...node.content);
    }
    return parts.join('').trim();
}
