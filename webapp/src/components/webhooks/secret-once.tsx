'use client';

import React, { useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';

/**
 * The signing secret of a webhook, shown once, right after it is created or
 * rotated. It lives only in this component's props: closing the notice drops it,
 * and the server never returns it again.
 */
export default function SecretOnce({ secret, host, rotated, onDone }: { secret: string; host: string; rotated?: boolean; onDone: () => void }) {
    const { t } = useTranslation('builder');
    const [copied, setCopied] = useState<'yes' | 'no' | null>(null);
    const input = useRef<HTMLInputElement>(null);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(secret);
            setCopied('yes');
        } catch {
            // no clipboard here (or it was refused): select it so Ctrl+C works
            input.current?.select();
            setCopied('no');
        }
    };

    return (
        <section className="flex flex-col gap-3 rounded-lg border border-brand-500 bg-brand-100 p-4" aria-labelledby="webhook-secret-title" data-testid="webhook-secret-once">
            <h3 id="webhook-secret-title" className="text-sm font-semibold text-black-900">
                {t(rotated ? 'WEBHOOKS.SECRET.TITLE_ROTATED' : 'WEBHOOKS.SECRET.TITLE', { host })}
            </h3>
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-800">{t('WEBHOOKS.SECRET.ONCE')}</p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <label htmlFor="webhook-secret-value" className="sr-only">
                    {t('WEBHOOKS.SECRET.LABEL')}
                </label>
                <input
                    ref={input}
                    id="webhook-secret-value"
                    readOnly
                    value={secret}
                    spellCheck={false}
                    autoComplete="off"
                    onFocus={(e) => e.currentTarget.select()}
                    className="h-10 w-full rounded-md border border-control bg-white px-3.5 font-mono text-sm text-black-900 sm:flex-1"
                />
                <Button type="button" variant="v2Button" size="sm" onClick={copy}>
                    {t('WEBHOOKS.SECRET.COPY')}
                </Button>
            </div>
            <p role="status" className="min-h-5 text-xs text-black-700">
                {copied === 'yes' ? t('WEBHOOKS.SECRET.COPIED') : copied === 'no' ? t('WEBHOOKS.SECRET.COPY_FAILED') : ''}
            </p>
            <p className="max-w-[62ch] text-xs leading-relaxed text-black-700">{t('WEBHOOKS.SECRET.VERIFY')}</p>
            <div>
                <Button type="button" size="sm" onClick={onDone}>
                    {t('WEBHOOKS.SECRET.DONE')}
                </Button>
            </div>
        </section>
    );
}
