'use client';

import React, { useId, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useGetAuditRetentionQuery, useSetAuditRetentionMutation } from '@app/store/workspaces/audit-retention-api';

const radioRow = 'flex min-h-11 cursor-pointer items-center gap-3 rounded border border-black-300 px-3 text-sm text-black-900 md:min-h-10';

/** The refusal's code from an RTK Query error (`data.code`), if the server sent one. */
function refusalCode(error: unknown): string {
    const data = (error as { data?: { code?: unknown } } | undefined)?.data;
    return typeof data?.code === 'string' ? data.code : '';
}

/**
 * How long the workspace keeps its activity entries (docs/audit-log.md): an owner chooses 6, 12, 24 or 60 months. It
 * draws nothing for anyone else (who still read the figure in the page's intro) and nothing until the server has said
 * the caller may change it, so a refused request is never one the page invited. A shorter period deletes nothing at
 * once: the dialog says the entries past it go at the next daily clean-up, and cannot be brought back.
 */
export function AuditRetentionSetting({ workspaceId }: { workspaceId: string }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const groupId = useId();
    const { data } = useGetAuditRetentionQuery(workspaceId, { skip: !workspaceId });
    const [save, { isLoading }] = useSetAuditRetentionMutation();
    const [open, setOpen] = useState(false);
    const [months, setMonths] = useState<number | null>(null);
    const [error, setError] = useState('');

    if (!data?.canChange) return null;

    const chosen = months ?? data.months;
    const shortening = chosen < data.months;
    const options = [...data.options].filter((option) => option >= data.minimumMonths).sort((a, b) => a - b);

    const close = () => {
        setOpen(false);
        setMonths(null);
        setError('');
    };

    const submit = async () => {
        setError('');
        const answer = await save({ workspaceId, months: chosen });
        if ('data' in answer && answer.data) {
            toast({ description: t(answer.data.appliesAtNextPurge ? 'AUDIT_LOG.SETTING.SAVED_SHORTER' : 'AUDIT_LOG.SETTING.SAVED', { count: answer.data.months }) });
            close();
            return;
        }
        const code = refusalCode((answer as { error?: unknown }).error);
        setError(t(code === 'audit_unavailable' ? 'AUDIT_LOG.SETTING.ERROR_UNRECORDED' : 'AUDIT_LOG.SETTING.ERROR'));
    };

    return (
        <>
            <Button type="button" variant="v2Button" size="sm" className="min-h-11 w-fit md:min-h-9" onClick={() => setOpen(true)}>
                {t('AUDIT_LOG.SETTING.CHANGE')}
            </Button>
            {open && (
                <Dialog open onOpenChange={(next) => !next && close()}>
                    <DialogContent className="max-w-lg" title={t('AUDIT_LOG.SETTING.TITLE')}>
                        <div className="flex flex-col gap-4 pr-6">
                            <div aria-hidden="true" className="text-lg font-semibold text-black-900">
                                {t('AUDIT_LOG.SETTING.TITLE')}
                            </div>
                            <p className="text-sm leading-relaxed text-black-700">{t('AUDIT_LOG.SETTING.INTRO', { count: data.minimumMonths })}</p>
                            <fieldset className="flex flex-col gap-2">
                                <legend className="mb-1 text-xs font-medium text-black-700">{t('AUDIT_LOG.SETTING.LEGEND')}</legend>
                                {options.map((option) => (
                                    <label key={option} className={radioRow}>
                                        <input type="radio" name={groupId} className="h-4 w-4" checked={chosen === option} onChange={() => setMonths(option)} />
                                        {t('AUDIT_LOG.SETTING.OPTION', { count: option })}
                                        {option === data.defaultMonths && <span className="text-xs text-black-700">{t('AUDIT_LOG.SETTING.DEFAULT')}</span>}
                                    </label>
                                ))}
                            </fieldset>
                            {shortening && (
                                <p role="status" className="rounded border border-black-300 bg-black-100 p-3 text-sm leading-relaxed text-black-900">
                                    {t('AUDIT_LOG.SETTING.SHORTENING', { count: chosen })}
                                </p>
                            )}
                            {error && (
                                <p role="alert" className="text-sm font-medium text-[#B42318]">
                                    {error}
                                </p>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button type="button" variant="v2Button" size="sm" onClick={close}>
                                    {t('AUDIT_LOG.SETTING.CANCEL')}
                                </Button>
                                <Button type="button" size="sm" isLoading={isLoading} disabled={chosen === data.months} onClick={() => void submit()}>
                                    {t(shortening ? 'AUDIT_LOG.SETTING.SAVE_SHORTER' : 'AUDIT_LOG.SETTING.SAVE')}
                                </Button>
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </>
    );
}
