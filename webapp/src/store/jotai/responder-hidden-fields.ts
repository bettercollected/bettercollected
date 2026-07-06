import { atom, useAtom } from 'jotai';

/**
 * Hidden-field (URL parameter) values captured when the public form loaded —
 * only names the form declares are ever captured (see utils/answer-piping.ts
 * `captureHiddenFieldValues`). Submitted with the response and used by answer
 * piping in question text.
 */
const hiddenFieldValuesAtom = atom<Record<string, string>>({});

export function useHiddenFieldValues() {
    const [hiddenValues, setHiddenValues] = useAtom(hiddenFieldValuesAtom);
    return { hiddenValues, setHiddenValues };
}
