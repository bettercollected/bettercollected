'use client';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';

import useRespondentLanguage from './use-respondent-language';

// A plain language tag ("nl", "en-GB", "pt-BR"): what `lang` accepts.
const LANGUAGE_TAG = /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i;

/**
 * The `lang` for text the form's author wrote (question titles,
 * descriptions, options), when it differs from the respondent's interface
 * language.
 *
 * The page (`<html lang>`) is in the interface language, so the chrome is
 * read right. The form's own text is marked only when the form declares its
 * language (`settings.language`) and that is not the interface language; a
 * form that declares nothing is taken to be in the page's language.
 */
export function formContentLanguage(declared: string | null | undefined, uiLanguage: string): string | undefined {
    const tag = declared?.trim();
    if (!tag || !LANGUAGE_TAG.test(tag)) return undefined;
    return tag.split('-')[0].toLowerCase() === uiLanguage.toLowerCase() ? undefined : tag;
}

/** formContentLanguage for the form being answered. */
export default function useFormContentLanguage(): string | undefined {
    const form = useAppSelector(selectForm);
    const { language } = useRespondentLanguage();
    return formContentLanguage(form?.settings?.language, language);
}
