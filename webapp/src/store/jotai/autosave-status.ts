import { atom, useAtom } from 'jotai';

import type { SaveQueueState } from '@app/utils/autosave-queue';

export type AutosaveState = SaveQueueState;

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

/** The short status line shown next to Undo/Redo (and in the flow view). */
export function autosaveStatusLabel(state: AutosaveState, t?: (key: string) => string): string | null {
    // With `t` (the builder's translation function) the line is read in the dashboard's language.
    const say = (key: string, english: string) => (t ? t(key) : english);
    switch (state) {
        case 'saving':
            return say('AUTOSAVE.SAVING', 'Saving…');
        case 'saved':
            return say('AUTOSAVE.SAVED', 'Saved');
        case 'retrying':
            return say('AUTOSAVE.RETRYING', 'Offline — retrying…');
        case 'error':
            return say('AUTOSAVE.ERROR', "Couldn't save — edit to retry");
        case 'conflict':
            return say('AUTOSAVE.CONFLICT', 'Not saved — changed elsewhere');
        default:
            return null;
    }
}

/** States the creator must notice: their latest edits are not stored. */
export function isAutosaveProblem(state: AutosaveState): boolean {
    return state === 'error' || state === 'retrying' || state === 'conflict';
}
