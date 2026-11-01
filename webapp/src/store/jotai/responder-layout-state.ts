import { atom, useAtomValue, useSetAtom } from 'jotai';

import type { StandardFormFieldDto } from '@app/models/dtos/form';
import { containerOfKey } from '@app/utils/layout-containers';

/**
 * What the respondent did with the layout containers of the form they are
 * filling (utils/layout-containers.ts): a panel opened or closed, the tab
 * shown, and the last thing said about a container ("Opened ... it has a
 * question that needs attention"). Keyed by form and container, so another
 * form's `c1` never reads this one's; absent means the creator's default
 * (a panel as the creator set it, the first tab).
 */
export interface ContainerView {
    open?: boolean;
    tab?: string;
    /** Said once, politely, in the container's own status region. */
    notice?: string;
}

const viewsAtom = atom<Record<string, ContainerView>>({});

const viewKey = (formId: string | undefined, containerId: string) => `${formId ?? ''}:${containerId}`;

export function useContainerView(formId: string | undefined, containerId: string): ContainerView | undefined {
    const views = useAtomValue(viewsAtom);
    return views[viewKey(formId, containerId)];
}

/** Change what the respondent did with one container. */
export function useSetContainerView(formId: string | undefined) {
    const set = useSetAtom(viewsAtom);
    return (containerId: string, patch: Partial<ContainerView>) => set((views) => ({ ...views, [viewKey(formId, containerId)]: { ...views[viewKey(formId, containerId)], ...patch } }));
}

/**
 * Open the panel / show the tab that holds the question an invalid-field key
 * belongs to, and say so once (in the container's own status region).
 * Nothing happens when it is already open or shown. Reads the state as it is
 * when called, so a late call (after a page change) is never stale. The
 * caller moves focus after the render (`flushSync`, see `useFocusProblem`).
 */
export function useRevealQuestion(formId: string | undefined, say: (kind: 'panel' | 'tab', title: string) => string) {
    const set = useSetAtom(viewsAtom);
    return (page: StandardFormFieldDto | undefined, key: string): void => {
        const found = containerOfKey(page, key);
        if (!found || found.container.type === 'fieldset') return;
        const { container, tabId } = found;
        const at = viewKey(formId, container.id);
        set((all) => {
            const current = all[at];
            if (container.type === 'tabs') {
                if (!tabId || (current?.tab ?? container.tabs?.[0]?.id) === tabId) return all;
                const title = container.tabs?.find((tab) => tab.id === tabId)?.title ?? '';
                return { ...all, [at]: { ...current, tab: tabId, notice: say('tab', title) } };
            }
            if (current?.open ?? !container.collapsed) return all;
            return { ...all, [at]: { ...current, open: true, notice: say('panel', container.title ?? '') } };
        });
    };
}
