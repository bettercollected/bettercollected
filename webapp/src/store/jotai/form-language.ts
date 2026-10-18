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
import { formDocAtom } from './form-document';

/** The document's language, or null when it declares none. */
export const formLanguageAtom = atom<string | null>((get) => (get(formDocAtom).settings as { language?: string | null } | undefined)?.language ?? null);

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
