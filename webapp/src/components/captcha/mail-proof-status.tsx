'use client';

/**
 * The polite live message by a "send" button while the automatic spam check is
 * still being calculated (after 1.5 seconds; shorter waits are silent). The live
 * region is always in the page and only its text changes, so assistive
 * technology announces it reliably. No new tab stop, no timeout to beat.
 */
export default function MailProofStatus({ waiting, text, lang }: { waiting: boolean; text: string; lang?: string }) {
    return (
        // sr-only while empty: the region stays in the page without taking room in the layout
        <p role="status" aria-live="polite" lang={lang} className={waiting ? 'body4 mt-3 text-black-700' : 'sr-only'} data-testid="mail-proof-status">
            {waiting ? text : null}
        </p>
    );
}
