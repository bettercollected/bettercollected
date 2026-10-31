import { atom, useAtom } from 'jotai';

/**
 * The selections the respondent page cleared because their option stopped
 * being available (utils/option-logic.ts), by question id: the texts of the
 * options that went, and what the question's selection was once they had
 * gone (`after`). The question says so under its options until the
 * respondent changes that selection.
 */
export type ClearedOptions = Record<string, { texts: string[]; after: string }>;

const clearedOptionsAtom = atom<ClearedOptions>({});

export function useClearedOptions() {
    const [cleared, setCleared] = useAtom(clearedOptionsAtom);
    return { cleared, setCleared };
}
