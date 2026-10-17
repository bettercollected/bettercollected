'use client';

import { atom, useAtom } from 'jotai';

import { formDocAtom } from './form-document';
import { EntityLocation, locationIndexAtom } from './form-document-selectors';

export type SetAtom<Args extends any[], Result> = (...args: Args) => Result;

export interface ActiveFormBuilderComponent {
    id: string;
    index: number;
}

type Selection = ActiveFormBuilderComponent | null;
type SelectionUpdate = Selection | ((prev: Selection) => Selection);

/**
 * Selection is by id: the index is looked up in the document, so it follows
 * the page or question when others move. The index given with the id is
 * used only when the document has no such page or question (the welcome and
 * ending pages, or a selection the document does not hold yet).
 */
function idFirstSelection(pick: (at: EntityLocation) => number | undefined, initial: Selection) {
    const selected = atom<Selection>(initial);
    // The same object as long as id and index stay the same, so that
    // subscribers do not re-render on every edit of the document.
    const derived = new WeakMap<ActiveFormBuilderComponent, ActiveFormBuilderComponent>();
    const current = atom(
        (get) => {
            const value = get(selected);
            if (!value?.id) return value;
            const at = get(locationIndexAtom).get(value.id);
            const index = at ? pick(at) : undefined;
            if (index === undefined || index === value.index) return value;
            const cached = derived.get(value);
            if (cached && cached.index === index) return cached;
            const next = { ...value, index };
            derived.set(value, next);
            return next;
        },
        (get, set, update: SelectionUpdate) => {
            set(selected, typeof update === 'function' ? update(get(current)) : update);
        }
    );
    return { selected, current };
}

const field = idFirstSelection((at) => (at.childIdx === undefined ? at.fieldIdx : undefined), null);
const slide = idFirstSelection((at) => (at.fieldIdx === undefined ? at.pageIdx : undefined), { id: 'welcome-page', index: -10 });

/** The selected question (id first; the index is where it is now on its page). */
export const activeFieldAtom = field.current;
/** The selected page (id first; the index is where it is now in the form). */
export const activeSlideAtom = slide.current;

/**
 * After undo or redo: the selected page follows the selected question to the
 * page it is on now (undoing a move to another page takes it back).
 */
export const followActiveFieldAtom = atom(null, (get, set) => {
    const field = get(activeFieldAtom);
    if (!field?.id) return;
    const at = get(locationIndexAtom).get(field.id);
    if (!at || at.fieldIdx === undefined) return;
    const page = get(formDocAtom).fields?.[at.pageIdx];
    if (page && get(activeSlideAtom)?.id !== page.id) set(activeSlideAtom, { id: page.id, index: at.pageIdx });
});

export function useActiveFieldComponent() {
    const [activeFieldComponent, setActiveFieldComponent] = useAtom(activeFieldAtom);

    return { activeFieldComponent, setActiveFieldComponent };
}

export function useActiveSlideComponent() {
    const [activeSlideComponent, setActiveSlideComponent] = useAtom(activeSlideAtom);
    return { activeSlideComponent, setActiveSlideComponent };
}

const activeThankYouPage = atom<ActiveFormBuilderComponent | null>({
    id: '',
    index: 0
});

export function useActiveThankYouPageComponent() {
    const [activeThankYouPageComponent, setActiveThankYouPageComponent] = useAtom(activeThankYouPage);
    return { activeThankYouPageComponent, setActiveThankYouPageComponent };
}

/** The ending shown when the selected one is gone: the default (marked, else the first). */
function defaultEnding(endings: Array<{ isDefault?: boolean }>): number {
    const marked = endings.findIndex((ending) => ending?.isDefault);
    return marked >= 0 ? marked : 0;
}

/**
 * After undo or redo: the selection follows the document. The selected page
 * follows the selected question, and when the selected ending is gone (an
 * undone "Add ending") the default ending is selected instead.
 */
export const followSelectionAtom = atom(null, (get, set) => {
    set(followActiveFieldAtom);
    const endings = get(formDocAtom).thankyouPage ?? [];
    const ending = get(activeThankYouPage);
    if (ending && !endings[ending.index]) {
        const index = defaultEnding(endings);
        set(activeThankYouPage, { id: `ending-${index}`, index });
    }
});
