'use client';

import { useTranslation } from 'react-i18next';

import type { RespondentLanguage } from '@app/lib/hooks/use-respondent-language';
import { cn } from '@app/shadcn/util/lib';

/**
 * The Sireto line on public and auth pages (DESIGN.md §10, Brand): who makes
 * bettercollected, and the trademark notice. A quiet caption, not a band —
 * it sits under the page's own content.
 *
 * In English, the app's language, unless the page is in the respondent's
 * (the responder portal passes `language`), in which case it says so with
 * `lang` too.
 */
export default function SiretoFooter({ className, language }: { className?: string; language?: RespondentLanguage }) {
    const { t } = useTranslation('respondent', { lng: language ?? 'en' });
    return (
        <footer className={cn('text-black-600 text-center text-xs leading-5', className)} lang={language}>
            <a href="https://sireto.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-brand-600">
                {t('SIRETO_FOOTER.PRODUCT_OF')}
            </a>
            <span aria-hidden="true"> · </span>
            <span>{t('SIRETO_FOOTER.TRADEMARK')}</span>
        </footer>
    );
}
