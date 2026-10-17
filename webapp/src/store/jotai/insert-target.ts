'use client';

import { atom, useAtom } from 'jotai';

/**
 * Where the canvas insert menu ("/", Ctrl/Cmd+K, the "+" between questions)
 * puts the new field. The menu opens next to `anchorId`'s element.
 */
export interface InsertTarget {
    slideId: string;
    slideIndex: number;
    /** The new field's position on the page. */
    fieldIndex: number;
    /** An empty text block the new field takes the place of ("/" typed in it). */
    replaceFieldId?: string;
    /** Element the menu is placed next to. */
    anchorId: string;
    /** Element focused again when the menu closes without inserting. */
    returnFocusId?: string;
}

export const insertTargetAtom = atom<InsertTarget | null>(null);

export function useInsertTarget() {
    const [insertTarget, setInsertTarget] = useAtom(insertTargetAtom);
    return { insertTarget, setInsertTarget };
}
