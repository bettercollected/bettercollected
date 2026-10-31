'use client';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { useClearedOptions } from '@app/store/jotai/responder-cleared-options';

/**
 * Says, under a choice question, that a selection was cleared because its
 * option is no longer available (the respondent changed an earlier answer
 * it depended on): "“Berlin” is no longer available, so it was removed from
 * your answer." A polite status region (always in the page, so that screen
 * readers announce the text when it appears), visible to everyone, gone as
 * soon as the question is answered again. Nothing for a question inside a
 * repeating-group item (option logic does not reach there).
 */
export default function OptionClearedNotice({ fieldId }: { fieldId: string }) {
    const { cleared } = useClearedOptions();
    const { t } = useRespondentLanguage();
    const texts = cleared[fieldId]?.texts ?? [];
    return (
        <p role="status" aria-live="polite" aria-atomic="true" data-testid={`option-cleared-${fieldId}`} className={texts.length ? 'text-[13px] leading-snug' : 'sr-only'}>
            {texts.length ? t('OPTIONS.CLEARED', { count: texts.length, options: texts.map((text) => `\u201c${text}\u201d`).join(', ') }) : null}
        </p>
    );
}
