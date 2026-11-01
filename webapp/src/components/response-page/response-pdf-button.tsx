'use client';

import { useRef, useState } from 'react';

import { FileDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { ResponseExportRefusal, useDownloadResponsePdfMutation } from '@app/store/workspaces/api';
import { downloadBlob, exportFileName } from '@app/utils/response-export';

/** The message key (and values) for a refused or failed PDF: the server's code first, then its status. */
export function pdfFailureMessage(error: any): { key: string; values?: Record<string, unknown> } {
    const data: ResponseExportRefusal = error?.data ?? {};
    const status = error?.status;
    if (data.code === 'export_busy') return { key: 'RESPONSE_PAGE.PDF_ERROR_BUSY' };
    if (status === 429 || data.code === 'rate_limited') return { key: 'RESPONSE_PAGE.PDF_ERROR_RATE_LIMITED', values: { minutes: Math.max(1, Math.ceil((data.retryAfter ?? 60) / 60)) } };
    if (status === 413 || data.code === 'pdf_too_large') return { key: 'RESPONSE_PAGE.PDF_ERROR_TOO_LARGE' };
    if (status === 403) return { key: 'RESPONSE_PAGE.PDF_ERROR_FORBIDDEN' };
    if (status === 404) return { key: 'RESPONSE_PAGE.PDF_ERROR_MISSING' };
    return { key: 'RESPONSE_PAGE.PDF_ERROR_GENERIC' };
}

/**
 * "Download PDF" on the response page: the server draws the one response when
 * asked (never stored), in the viewer's language and time zone, and the browser
 * saves it under the name the server offers (docs/response-export.md). Nothing of
 * the response is kept here: the file goes straight to the download.
 */
export default function ResponsePdfButton({ workspaceId, responseId, formTitle }: { workspaceId: string; responseId: string; formTitle: string }) {
    const { t, i18n } = useTranslation();
    const { toast } = useToast();
    const [download, { isLoading, reset }] = useDownloadResponsePdfMutation();
    const [busy, setBusy] = useState(false);
    // a second click while the first PDF is being made is ignored (the button is disabled, but a held key repeats)
    const running = useRef(false);

    const handleClick = async () => {
        if (running.current) return;
        running.current = true;
        setBusy(true);
        try {
            let zone: string | undefined;
            try {
                zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            } catch {
                zone = undefined;
            }
            const file = await download({ workspaceId, responseId, lang: i18n.language, tz: zone }).unwrap();
            downloadBlob(file.blob, file.fileName || exportFileName(formTitle, 'pdf'));
            toast({ description: t('RESPONSE_PAGE.PDF_DONE') });
            // the store keeps a mutation's result: let go of the response's PDF now it is saved
            reset();
        } catch (error: any) {
            const failure = pdfFailureMessage(error);
            toast({ description: t(failure.key, failure.values), variant: 'destructive' });
            reset();
        } finally {
            running.current = false;
            setBusy(false);
        }
    };

    const working = busy || isLoading;
    return (
        <Button variant="ghost" className="min-w-9 px-2!" title={t('RESPONSE_PAGE.PDF')} disabled={working} aria-busy={working} onClick={handleClick}>
            <FileDown className="h-4 w-4 shrink-0 sm:mr-1.5" aria-hidden="true" />
            <span className="sr-only sm:not-sr-only">{working ? t('RESPONSE_PAGE.PDF_PREPARING') : t('RESPONSE_PAGE.PDF')}</span>
        </Button>
    );
}
