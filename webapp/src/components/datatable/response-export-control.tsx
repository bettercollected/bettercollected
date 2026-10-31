import { useCallback, useEffect, useRef, useState } from 'react';

import { DownloadIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { responseExportLocale } from '@app/constants/locales/response-export';
import { Button } from '@app/shadcn/components/ui/button';
import { ResponseExportDto, ResponseExportRefusal, useDownloadResponseExportMutation, useGetResponseExportQuery, useGetResponseExportsQuery, useStartResponseExportMutation } from '@app/store/workspaces/api';
import { downloadBlob, exportExtension, exportFileName } from '@app/utils/response-export';

/** How often a running export is asked about. */
export const EXPORT_POLL_MS = 3000;

type Phase = 'idle' | 'starting' | 'preparing' | 'ready' | 'downloading' | 'done' | 'error';

interface Props {
    workspaceId: string;
    formId: string;
    formTitle: string;
    /** the responses list's search, in force: the export holds what the list shows */
    search?: string;
}

/** A message key (and its values) for what went wrong: the server's code first, then its status. */
function refusalMessage(error: any): { key: string; values?: Record<string, unknown> } {
    const data: ResponseExportRefusal = error?.data ?? {};
    const status = error?.status;
    if (status === 429 || data.code === 'rate_limited') return { key: responseExportLocale.errorRateLimited, values: { minutes: Math.max(1, Math.ceil((data.retryAfter ?? 60) / 60)) } };
    if (data.code === 'export_in_progress') return { key: responseExportLocale.errorInProgress };
    if (data.code === 'too_many_rows' || status === 413) return { key: responseExportLocale.errorTooMany };
    if (data.code === 'export_gone' || data.code === 'link_expired' || status === 410) return { key: responseExportLocale.errorGone };
    if (status === 403) return { key: responseExportLocale.errorForbidden };
    return { key: responseExportLocale.errorGeneric };
}

/** Why an export that ended without a file did: its status and error code. */
function endedMessage(exportRow: ResponseExportDto): string {
    if (exportRow.status === 'cancelled') return exportRow.errorCode === 'permission_removed' ? responseExportLocale.errorPermission : responseExportLocale.errorDeleted;
    if (exportRow.status === 'failed') return exportRow.errorCode === 'too_large' ? responseExportLocale.errorTooLarge : responseExportLocale.errorFailed;
    return responseExportLocale.errorGone;
}

/**
 * The Export button of a form's responses, and what follows: the file of a
 * small export downloads at once; a large one is prepared by the server
 * ("We're preparing your export"), found again after a reload, and handed over
 * through a short-lived link once it is ready (docs/response-export.md).
 */
export default function ResponseExportControl({ workspaceId, formId, formTitle, search }: Props) {
    const { t } = useTranslation();
    const [phase, setPhase] = useState<Phase>('idle');
    const [exportId, setExportId] = useState<string | undefined>();
    const [message, setMessage] = useState<{ key: string; values?: Record<string, unknown> } | undefined>();
    const [startExport] = useStartResponseExportMutation();
    const [downloadExport] = useDownloadResponseExportMutation();
    const mounted = useRef(true);
    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
        };
    }, []);

    // An export of this person's that is running or ready, from before a reload.
    const { data: mine, refetch: refetchMineQuery } = useGetResponseExportsQuery({ workspaceId, formId }, { skip: !workspaceId || !formId });
    const refetchMine = async (): Promise<ResponseExportDto[] | undefined> => {
        try {
            return await refetchMineQuery().unwrap();
        } catch {
            return undefined;
        }
    };
    const adopted = useRef(false);
    useEffect(() => {
        if (adopted.current || !mine || phase !== 'idle') return;
        const open = mine.find((row) => row.status === 'queued' || row.status === 'running' || row.status === 'ready');
        if (open) {
            adopted.current = true;
            setExportId(open.id);
            setPhase(open.status === 'ready' ? 'ready' : 'preparing');
            return;
        }
        // one that ended without a file, still worth a word
        const ended = mine[0];
        if (ended && (ended.status === 'failed' || ended.status === 'cancelled')) {
            adopted.current = true;
            setMessage({ key: endedMessage(ended) });
            setPhase('error');
        }
    }, [mine, phase]);

    // Follow the running export; a ready one is asked about again for a fresh link when downloaded.
    const following = !!exportId && (phase === 'preparing' || phase === 'ready' || phase === 'downloading');
    const { data: followed, refetch } = useGetResponseExportQuery({ workspaceId, formId, exportId: exportId ?? '' }, { skip: !following, pollingInterval: phase === 'preparing' ? EXPORT_POLL_MS : 0 });
    useEffect(() => {
        if (!followed || followed.id !== exportId || (phase !== 'preparing' && phase !== 'ready')) return;
        if (followed.status === 'ready') setPhase('ready');
        else if (followed.status === 'queued' || followed.status === 'running') setPhase('preparing');
        else if (followed.status === 'downloaded') setPhase('done');
        else {
            setMessage({ key: endedMessage(followed) });
            setPhase('error');
        }
    }, [followed, exportId, phase]);

    const handleStart = useCallback(async () => {
        setMessage(undefined);
        setPhase('starting');
        try {
            const started = await startExport({ workspaceId, formId, ...(search ? { search } : {}) }).unwrap();
            if (!mounted.current) return;
            if (started.kind === 'file') {
                // small enough to come in the response itself: nothing was stored
                downloadBlob(started.blob, exportFileName(formTitle, exportExtension(started.mediaType)));
                setPhase('done');
                return;
            }
            setExportId(started.export.id);
            setPhase('preparing');
        } catch (error: any) {
            if (!mounted.current) return;
            if (error?.data?.code === 'export_in_progress') {
                // follow the one that is already running
                const open = (await refetchMine())?.find((row) => row.status === 'queued' || row.status === 'running');
                if (open && mounted.current) {
                    setExportId(open.id);
                    setPhase('preparing');
                    return;
                }
            }
            setMessage(refusalMessage(error));
            setPhase('error');
        }
    }, [workspaceId, formId, formTitle, search, startExport]);

    const handleDownload = useCallback(async () => {
        if (!exportId) return;
        setPhase('downloading');
        try {
            // the link is short-lived: ask for a fresh one
            const fresh = await refetch().unwrap();
            if (!fresh.downloadUrl) {
                setMessage({ key: endedMessage(fresh) });
                setPhase('error');
                return;
            }
            const blob = await downloadExport({ downloadUrl: fresh.downloadUrl }).unwrap();
            if (!mounted.current) return;
            downloadBlob(blob, fresh.fileName || exportFileName(formTitle, fresh.format));
            setMessage({ key: responseExportLocale.deletedAfterDownload });
            setPhase('done');
        } catch (error: any) {
            if (!mounted.current) return;
            setMessage(refusalMessage(error));
            setPhase('error');
        }
    }, [exportId, refetch, downloadExport, formTitle]);

    const handleDismiss = () => {
        setPhase('idle');
        setMessage(undefined);
        setExportId(undefined);
    };

    const busy = phase === 'starting' || phase === 'preparing' || phase === 'downloading';
    const expires = followed?.expiresAt ? new Date(followed.expiresAt).toLocaleString() : undefined;

    return (
        <div className="flex flex-col items-start gap-2 sm:items-end">
            <Button data-umami-event="Export CSV Button" isLoading={phase === 'starting'} disabled={busy} aria-describedby="response-export-status" variant="v2Button" icon={<DownloadIcon className="h-4 w-4" />} onClick={handleStart}>
                {t(search ? responseExportLocale.buttonMatching : responseExportLocale.button)}
            </Button>
            <div id="response-export-status" role={phase === 'error' ? 'alert' : 'status'} aria-live={phase === 'error' ? 'assertive' : 'polite'} aria-busy={busy} className="max-w-[420px] text-left text-sm text-black-700 sm:text-right">
                {phase === 'starting' && <span>{t(responseExportLocale.starting)}</span>}
                {phase === 'preparing' && <span>{t(responseExportLocale.preparing)}</span>}
                {phase === 'downloading' && <span>{t(responseExportLocale.downloading)}</span>}
                {phase === 'ready' && (
                    <div className="flex flex-col items-start gap-2 sm:items-end">
                        <span>{t(responseExportLocale.ready)}</span>
                        {expires && <span className="text-xs text-black-600">{t(responseExportLocale.readyUntil, { time: expires })}</span>}
                        <Button type="button" variant="primary" size="sm" icon={<DownloadIcon className="h-4 w-4" />} onClick={handleDownload}>
                            {t(responseExportLocale.download)}
                        </Button>
                    </div>
                )}
                {(phase === 'done' || phase === 'error') && (
                    <div className="flex flex-col items-start gap-1 sm:items-end">
                        {phase === 'done' && <span>{t(responseExportLocale.downloaded)}</span>}
                        {message && <span>{t(message.key, message.values)}</span>}
                        <button type="button" onClick={handleDismiss} className="text-xs text-brand-500 underline">
                            {t(responseExportLocale.dismiss)}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
