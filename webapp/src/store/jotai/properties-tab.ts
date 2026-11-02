import { atom, useAtom } from 'jotai';

export type PropertiesTab = 'page' | 'form' | 'design' | 'ai';

/**
 * Which tab the right-hand properties drawer shows. Controlled state (rather
 * than the Tabs component's internal default) so other builder surfaces can
 * deep-link into a tab — e.g. the empty trust-strip nudge on the canvas jumps
 * straight to the Form tab.
 */
const propertiesTabAtom = atom<PropertiesTab>('page');

export function usePropertiesTab() {
    const [propertiesTab, setPropertiesTab] = useAtom(propertiesTabAtom);
    return { propertiesTab, setPropertiesTab };
}

/** The tabs a link may open (`/edit?tab=form`); the AI tab is left to the person using the builder. */
const LINKABLE_TABS: ReadonlyArray<PropertiesTab> = ['page', 'form', 'design'];

/** The tab a `?tab=` value names, or null for anything else (a missing or unknown value changes nothing). */
export function propertiesTabFromParam(value: string | null | undefined): PropertiesTab | null {
    return LINKABLE_TABS.find((tab) => tab === value) ?? null;
}
