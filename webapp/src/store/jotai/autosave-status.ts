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
export function autosaveStatusLabel(state: AutosaveState): string | null {
    switch (state) {
        case 'saving':
            return 'Saving…';
        case 'saved':
            return 'Saved';
        case 'retrying':
            return 'Offline — retrying…';
        case 'error':
            return "Couldn't save — edit to retry";
        case 'conflict':
            return 'Not saved — changed elsewhere';
        default:
            return null;
    }
}

/** States the creator must notice: their latest edits are not stored. */
export function isAutosaveProblem(state: AutosaveState): boolean {
    return state === 'error' || state === 'retrying' || state === 'conflict';
}
