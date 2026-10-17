'use client';

import { useTranslation } from 'react-i18next';

import { localesCommon } from '@app/constants/locales/common';
import { cn } from '@app/shadcn/util/lib';

/**
 * The Sireto line on public and auth pages (DESIGN.md §10, Brand): who makes
 * bettercollected, and the trademark notice. A quiet caption, not a band —
 * it sits under the page's own content.
 */
export default function SiretoFooter({ className }: { className?: string }) {
    const { t } = useTranslation();
    return (
        <footer className={cn('text-black-600 text-center text-xs leading-5', className)}>
            <a href="https://sireto.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-brand-600">
                {t(localesCommon.siretoFooter.productOf)}
            </a>
            <span aria-hidden="true"> · </span>
            <span>{t(localesCommon.siretoFooter.trademark)}</span>
        </footer>
    );
}
