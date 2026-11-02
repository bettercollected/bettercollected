'use client';

import React, { useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Checkbox } from '@app/shadcn/components/ui/checkbox';

/**
 * The ten recovery codes, shown once. They exist in the page only as long as
 * this component does: they are held in its props, written to nothing (no
 * storage, no store, no log) and the server never returns them again. Copying
 * or saving them is the user's own act.
 */
export default function RecoveryCodes({ codes, acknowledged, onAcknowledge }: { codes: string[]; acknowledged: boolean; onAcknowledge: (value: boolean) => void }) {
    const { t } = useTranslation();
    const [message, setMessage] = useState('');
    const list = useRef<HTMLOListElement>(null);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(codes.join('\n'));
            setMessage(t('STAFF.MFA.CODES.COPIED'));
        } catch {
            // no clipboard (or it was refused): select the list so that Ctrl+C works
            const selection = window.getSelection();
            if (list.current && selection) {
                selection.selectAllChildren(list.current);
            }
            setMessage(t('STAFF.MFA.CODES.COPY_FAILED'));
        }
    };

    const download = () => {
        const text = `${t('STAFF.MFA.CODES.FILE_TITLE')}\n\n${codes.join('\n')}\n`;
        const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = 'bettercollected-recovery-codes.txt';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setMessage(t('STAFF.MFA.CODES.DOWNLOADED'));
    };

    return (
        <div className="flex flex-col gap-4">
            <p className="text-sm leading-relaxed text-black-800">{t('STAFF.MFA.CODES.INTRO')}</p>
            <ol ref={list} aria-label={t('STAFF.MFA.CODES.LIST_LABEL')} className="grid grid-cols-1 gap-x-6 gap-y-1.5 rounded border border-black-300 bg-black-100 p-4 font-mono text-sm sm:grid-cols-2">
                {codes.map((code) => (
                    <li key={code} className="tracking-wider text-black-900">
                        {code}
                    </li>
                ))}
            </ol>
            <div className="flex flex-wrap gap-2">
                <Button type="button" variant="v2Button" size="sm" onClick={copy}>
                    {t('STAFF.MFA.CODES.COPY')}
                </Button>
                <Button type="button" variant="v2Button" size="sm" onClick={download}>
                    {t('STAFF.MFA.CODES.DOWNLOAD')}
                </Button>
            </div>
            <p role="status" className="min-h-4 text-xs text-black-700">
                {message}
            </p>
            <div className="flex items-start gap-2.5">
                <Checkbox id="recovery-codes-stored" checked={acknowledged} onCheckedChange={(value) => onAcknowledge(value === true)} className="mt-0.5 shrink-0" />
                <label htmlFor="recovery-codes-stored" className="text-sm leading-relaxed text-black-900">
                    {t('STAFF.MFA.CODES.STORED')}
                </label>
            </div>
        </div>
    );
}
