'use client';

import { useId } from 'react';

import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';

import { FORM_LANGUAGES, formLanguageName } from '@app/lib/form-ops';
import { isLanguageTag } from '@app/lib/hooks/use-form-content-language';
import { dispatchAtom } from '@app/store/jotai/form-document';
import { formLanguageAtom } from '@app/store/jotai/form-language';
import { InspectorSection } from '@app/views/molecules/form-builder/inspector-controls';

/**
 * "Form language": the language the form's questions are written in
 * (`settings.language`). Respondent pages mark the form's own text with it
 * when it is not the page's language, so screen readers and browsers read
 * it right. A change is the op `set_form_language` on the builder's
 * document (one undo step), saved with the form.
 */
export default function FormLanguageSetting() {
    const { t } = useTranslation('builder');
    const id = useId();
    const language = useAtomValue(formLanguageAtom);
    const dispatch = useSetAtom(dispatchAtom);
    // A language set elsewhere that is not on the list (some imports set
    // "en-GB"): shown as it is, so the select never claims another one.
    const other = language != null && !formLanguageName(language) ? language : null;

    return (
        <InspectorSection title={t('FORM_LANGUAGE.TITLE')}>
            <div className="flex flex-col gap-1">
                <label htmlFor={id} className="text-xs text-black-700">
                    {t('FORM_LANGUAGE.LABEL')}
                </label>
                <select
                    id={id}
                    value={language ?? ''}
                    aria-describedby={`${id}-hint`}
                    onChange={(event) => dispatch({ ops: [{ op: 'set_form_language', language: event.target.value || null }], label: t('FORM_LANGUAGE.LABEL') })}
                    className="h-8 w-full rounded border border-control bg-white px-2 py-0 text-xs focus:border-brand-500"
                >
                    <option value="">{t('FORM_LANGUAGE.NOT_SET')}</option>
                    {other && (
                        <option value={other} lang={isLanguageTag(other) ? other : undefined}>
                            {other}
                        </option>
                    )}
                    {FORM_LANGUAGES.map(({ code, name }) => (
                        <option key={code} value={code} lang={code}>
                            {name}
                        </option>
                    ))}
                </select>
                <p id={`${id}-hint`} className="text-[11px] leading-relaxed text-black-600">
                    {t('FORM_LANGUAGE.HINT')}
                </p>
            </div>
        </InspectorSection>
    );
}
