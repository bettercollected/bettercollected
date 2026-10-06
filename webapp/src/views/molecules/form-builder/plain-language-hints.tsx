'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { TFunction } from 'i18next';
import { Lightbulb, X } from 'lucide-react';
import { useDebounceValue } from 'usehooks-ts';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { PlainLanguageHint, checkPlainLanguage } from '@app/utils/plain-language';

/**
 * Plain-language (B1) tips under a question's title or description.
 *
 * Advisory only: nothing here touches the form, so saving and publishing are
 * never blocked. The check runs on the debounced text; the polite live region
 * speaks only when the set of tips changes, not on every keystroke. The
 * element with `id` holds the tips as text, for the input's
 * `aria-describedby`.
 */

const STORAGE_PREFIX = 'bc.plainLanguage.dismissed';
// Fallback when localStorage is unavailable (private mode, blocked storage):
// dismissals then last for this page session.
const memoryDismissals = new Map<string, string[]>();

function readDismissed(key: string): string[] {
    try {
        const raw = window.localStorage.getItem(key);
        const parsed = raw ? JSON.parse(raw) : null;
        if (Array.isArray(parsed)) return parsed.filter((value): value is string => typeof value === 'string');
    } catch {
        // Storage blocked or corrupt: use the in-memory copy.
    }
    return memoryDismissals.get(key) ?? [];
}

function writeDismissed(key: string, ids: string[]) {
    memoryDismissals.set(key, ids);
    try {
        window.localStorage.setItem(key, JSON.stringify(ids));
    } catch {
        // Keep the in-memory copy only.
    }
}

export function plainLanguageHintMessage(t: TFunction, hint: PlainLanguageHint): string {
    switch (hint.rule) {
        case 'long-sentence':
            return t('PLAIN_LANGUAGE.LONG_SENTENCE', { words: hint.words, limit: hint.limit });
        case 'passive':
            return t(hint.language === 'en' ? 'PLAIN_LANGUAGE.PASSIVE_EN' : 'PLAIN_LANGUAGE.PASSIVE_NL', { match: hint.match });
        case 'jargon':
            return t('PLAIN_LANGUAGE.JARGON', { match: hint.match, suggestion: hint.suggestion });
        case 'double-question':
            if (hint.variant === 'and-or') return t('PLAIN_LANGUAGE.AND_OR', { match: hint.match });
            if (hint.variant === 'joined-questions') return t('PLAIN_LANGUAGE.JOINED_QUESTIONS', { match: hint.match });
            return t('PLAIN_LANGUAGE.TWO_QUESTIONS');
        default:
            return '';
    }
}

export interface PlainLanguageHintsProps {
    /** Id of the tips' text, referenced by the input's `aria-describedby`. */
    id: string;
    /** Title (TipTap JSON or string) or description text to check. */
    value: unknown;
    /** Form id, to remember dismissed tips per form. */
    formId?: string;
    /** The form's declared language (`settings.language`), if any. */
    formLanguage?: string | null;
    debounceMs?: number;
}

export default function PlainLanguageHints({ id, value, formId, formLanguage, debounceMs = 400 }: PlainLanguageHintsProps) {
    const { t } = useBuilderTranslation();
    const [debouncedValue] = useDebounceValue(value, debounceMs);
    const storageKey = `${STORAGE_PREFIX}:${formId ?? 'form'}:${id}`;
    const [dismissed, setDismissed] = useState<string[]>(() => readDismissed(storageKey));

    const hints = useMemo(() => checkPlainLanguage(debouncedValue, { formLanguage }), [debouncedValue, formLanguage]);
    const visible = hints.filter((hint) => !dismissed.includes(hint.id));
    const messages = visible.map((hint) => plainLanguageHintMessage(t, hint));

    // Announce when the set of tips changes — not on mount (focus already reads
    // them via aria-describedby) and not while the text is unchanged.
    const signature = visible.map((hint) => hint.id).join('|');
    const previousSignature = useRef(signature);
    const [announcement, setAnnouncement] = useState('');
    useEffect(() => {
        if (signature === previousSignature.current) return;
        previousSignature.current = signature;
        setAnnouncement(visible.length ? t('PLAIN_LANGUAGE.ANNOUNCE', { count: visible.length }) : '');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [signature]);

    const dismiss = (hintId: string) => {
        const next = [...dismissed.filter((existing) => hints.some((hint) => hint.id === existing)), hintId];
        setDismissed(next);
        writeDismissed(storageKey, next);
    };

    return (
        <div className="w-full" data-testid="plain-language-hints">
            <div id={id} hidden>
                {messages.join(' ')}
            </div>
            <p className="sr-only" aria-live="polite" aria-atomic="true">
                {announcement}
            </p>
            {visible.length > 0 && (
                <div className="mt-2 flex w-full flex-col gap-1">
                    <p className="text-xs text-black-500">{t('PLAIN_LANGUAGE.INTRO')}</p>
                    <ul aria-label={t('PLAIN_LANGUAGE.LABEL')} className="flex flex-col gap-1">
                        {visible.map((hint, index) => (
                            <li key={hint.id} className="flex items-start gap-2 rounded-md bg-black-100 px-2.5 py-1.5 text-sm leading-snug text-black-700">
                                <Lightbulb aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                                <span className="min-w-0 flex-1">{messages[index]}</span>
                                <button
                                    type="button"
                                    aria-label={t('PLAIN_LANGUAGE.DISMISS')}
                                    title={t('PLAIN_LANGUAGE.DISMISS')}
                                    className="-mr-1 shrink-0 rounded p-0.5 text-black-500 hover:bg-black-200 hover:text-black-800"
                                    onClick={() => dismiss(hint.id)}
                                >
                                    <X aria-hidden="true" className="h-3.5 w-3.5" />
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
