'use client';

/**
 * The form's own language (`settings.language`) in the builder: the
 * document holds it, changed through the op `set_form_language` (one undo
 * step) and saved with the form by autosave. The respondent views and the
 * plain-language tips read it from the Redux form, which follows the
 * document here.
 */
import { useEffect } from 'react';

import { atom, useAtomValue } from 'jotai';

import { selectForm, setFormLanguage } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

import { useBuilderHydration } from './builder-hydration';
import { FormDocument, formDocAtom } from './form-document';

/** The document's language, or null when it declares none. */
export const formLanguageAtom = atom<string | null>((get) => (get(formDocAtom).settings as { language?: string | null } | undefined)?.language ?? null);

/**
 * After a save that sent `sent`, the language the server stored (`saved`):
 * when the server kept another one (it does for a tag that cannot be set,
 * e.g. after an undo back to an imported "en-GB") and the document still
 * holds what was sent, the document takes the stored language, as a remote
 * change: no undo step. A language changed since the save stays.
 */
export const adoptSavedLanguageAtom = atom(null, (get, set, { sent, saved }: { sent: string | null; saved: string | null }) => {
    const doc = get(formDocAtom);
    const current = (doc.settings as { language?: string | null } | undefined)?.language ?? null;
    if (current !== sent || saved === sent) return false;
    set(formDocAtom, { ...doc, settings: { ...doc.settings, language: saved } } as FormDocument);
    return true;
});

/**
 * Keep the Redux form's language on the document's, once the builder holds
 * the form (before that, the document is still the empty one).
 */
export function useFormLanguageSync() {
    const language = useAtomValue(formLanguageAtom);
    const { hydratedFormId } = useBuilderHydration();
    const form = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    const holds = !!form?.formId && hydratedFormId === form.formId;
    const current = form?.settings?.language ?? null;
    useEffect(() => {
        if (holds && current !== language) dispatch(setFormLanguage(language));
    }, [holds, current, language, dispatch]);
}
