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
