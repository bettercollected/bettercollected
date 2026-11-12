'use client';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';

/**
 * The polite live message by the submit button while the automatic spam check
 * is still being calculated (after 1.5 seconds; shorter waits are silent). The
 * live region is always in the page and only its text changes, so assistive
 * technology announces it reliably. No new tab stop, no timeout to beat.
 */
export default function CaptchaStatus({ waiting }: { waiting: boolean }) {
    const { t, language } = useRespondentLanguage();
    return (
        // sr-only while empty: the region stays in the page without taking room in the layout
        <p role="status" aria-live="polite" lang={language} className={waiting ? 'text-[15px] leading-relaxed' : 'sr-only'} data-testid="captcha-status">
            {waiting ? t('NAV.CAPTCHA_WAITING') : null}
        </p>
    );
}
