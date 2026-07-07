import { atom, useAtom } from 'jotai';

export type AutosaveState = 'idle' | 'saving' | 'saved' | 'error';

interface IAutosaveStatus {
    state: AutosaveState;
    /** Epoch ms of the last successful save. */
    savedAt?: number;
}

/**
 * Written by AutoSaveForm, read by the builder navbar. Autosave used to be
 * completely silent — success and failure alike — which is the wrong posture
 * for a product whose pitch is "trust us with your data".
 */
const autosaveStatusAtom = atom<IAutosaveStatus>({ state: 'idle' });

export function useAutosaveStatus() {
    const [autosaveStatus, setAutosaveStatus] = useAtom(autosaveStatusAtom);
    return { autosaveStatus, setAutosaveStatus };
}
