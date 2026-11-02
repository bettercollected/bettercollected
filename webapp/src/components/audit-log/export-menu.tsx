'use client';

import React, { useState } from 'react';

import { ChevronDown, Download } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import { AuditExportFormat, requestAuditExport, saveBlob } from '@app/store/workspaces/audit-export';

/** The words for a refusal, by the server's code. */
const REFUSALS: Record<string, string> = {
    too_many_rows: 'AUDIT_LOG.EXPORT.TOO_MANY',
    rate_limited: 'AUDIT_LOG.EXPORT.RATE_LIMITED',
    audit_unavailable: 'AUDIT_LOG.EXPORT.UNRECORDED',
    http_403: 'AUDIT_LOG.EXPORT.FORBIDDEN'
};

/**
 * "Export" on the Activity page (docs/audit-log.md): the entries of the filters on screen as a CSV or JSON file. A real
 * button that opens the app's Radix menu (arrow keys, Escape returns focus to the button). The server records the
 * export before it sends the file; the page says so, and says why when it refuses (too many entries, too many
 * exports, not recorded) so the reader knows what to change. Nothing is held in memory but the one file.
 */
export function AuditExportMenu({ workspaceId, formId, query }: { workspaceId: string; formId?: string; query: string }) {
    const { t } = useTranslation();
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState<{ kind: 'done' | 'error'; text: string } | null>(null);

    const run = async (format: AuditExportFormat) => {
        if (busy || !workspaceId) return;
        setBusy(true);
        setMessage(null);
        const result = await requestAuditExport({ workspaceId, formId, query, format });
        setBusy(false);
        if (result.ok) {
            saveBlob(result.fileName, result.blob);
            setMessage({ kind: 'done', text: t('AUDIT_LOG.EXPORT.DONE', { file: result.fileName }) });
        } else {
            setMessage({ kind: 'error', text: t(REFUSALS[result.code] ?? 'AUDIT_LOG.EXPORT.ERROR') });
        }
    };

    return (
        <div className="flex flex-col gap-2">
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button type="button" variant="v2Button" size="sm" disabled={busy} className="min-h-11 w-fit md:min-h-9">
                        <Download className="mr-1.5 h-4 w-4" aria-hidden="true" />
                        {busy ? t('AUDIT_LOG.EXPORT.WORKING') : t('AUDIT_LOG.EXPORT.BUTTON')}
                        <ChevronDown className="ml-1 h-4 w-4" aria-hidden="true" />
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-[260px] rounded bg-white p-0" align="start">
                    <DropdownMenuItem className="hover:bg-black-100 flex min-h-11 cursor-pointer items-center px-4 py-3 text-sm" onSelect={() => void run('csv')}>
                        {t('AUDIT_LOG.EXPORT.CSV')}
                    </DropdownMenuItem>
                    <DropdownMenuItem className="hover:bg-black-100 flex min-h-11 cursor-pointer items-center px-4 py-3 text-sm" onSelect={() => void run('json')}>
                        {t('AUDIT_LOG.EXPORT.JSON')}
                    </DropdownMenuItem>
                    <p className="border-black-200 text-black-700 border-t px-4 py-3 text-xs leading-relaxed">{t('AUDIT_LOG.EXPORT.NOTE')}</p>
                </DropdownMenuContent>
            </DropdownMenu>
            <div role="status" aria-live="polite" className="max-w-[62ch] text-sm">
                {message?.kind === 'done' && <span className="text-black-700">{message.text}</span>}
            </div>
            {message?.kind === 'error' && (
                <p role="alert" className="max-w-[62ch] text-sm font-medium text-[#B42318]">
                    {message.text}
                </p>
            )}
        </div>
    );
}
