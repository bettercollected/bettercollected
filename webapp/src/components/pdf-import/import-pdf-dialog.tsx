'use client';

import React, { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useRouter } from 'next-nprogress-bar';

import { AIOptIn } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useGetPdfImportAiQuery, useStartPdfImportMutation } from '@app/store/redux/pdf-import-api';
import { startErrorKey, validateUpload } from '@app/utils/pdf-import';

interface ImportPdfDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    workspaceId: string;
    workspaceName: string;
}

/** Upload a PDF (or a photo of a paper form) and follow its import. */
export default function ImportPdfDialog({ open, onOpenChange, workspaceId, workspaceName }: ImportPdfDialogProps) {
    const router = useRouter();
    const { t } = useTranslation('builder');
    const input = useRef<HTMLInputElement>(null);
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [dragging, setDragging] = useState(false);
    const [startImport, { isLoading }] = useStartPdfImportMutation();
    const { data: ai, refetch: refetchAi } = useGetPdfImportAiQuery({ workspaceId }, { skip: !open || !workspaceId });
    // both the workspace opt-in (#715) and this upload's tick are needed
    const aiUsable = !!ai?.available && !!ai?.enabled;
    // unchecked by default: nothing goes to the AI provider without a tick
    const [aiConsent, setAiConsent] = useState(false);

    const choose = (chosen: File | undefined | null) => {
        if (!chosen) return;
        const problem = validateUpload(chosen);
        setError(problem);
        setFile(problem ? null : chosen);
    };

    const submit = async () => {
        if (!file) return;
        const result: any = await startImport({ workspaceId, file, aiConsent: aiConsent && aiUsable });
        if (result.data?.id) {
            onOpenChange(false);
            router.push(`/${workspaceName}/dashboard/forms/import/${result.data.id}`);
            return;
        }
        const detail = result.error?.data;
        const key = startErrorKey(detail?.code);
        setError(key ? t(key) : detail?.message || (typeof detail === 'string' ? detail : null) || t('PDF_IMPORT.START_ERROR.upload_failed'));
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg bg-white" title={t('PDF_IMPORT.DIALOG.TITLE')}>
                <DialogHeader>
                    <DialogTitle>{t('PDF_IMPORT.DIALOG.TITLE')}</DialogTitle>
                    <DialogDescription>{t('PDF_IMPORT.DIALOG.INTRO')}</DialogDescription>
                </DialogHeader>
                <button
                    type="button"
                    onClick={() => input.current?.click()}
                    onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        choose(e.dataTransfer.files?.[0]);
                    }}
                    className={`flex h-36 w-full flex-col items-center justify-center rounded-lg border-2 border-dashed text-sm transition ${dragging ? 'border-blue-500 bg-blue-50' : 'border-black-300 hover:border-blue-400'}`}
                >
                    {file ? (
                        <>
                            <span className="font-medium text-black-800">{file.name}</span>
                            <span className="mt-1 text-xs text-black-600">{t('PDF_IMPORT.DIALOG.CHOSEN', { size: (file.size / 1024 / 1024).toFixed(1) })}</span>
                        </>
                    ) : (
                        <>
                            <span className="font-medium text-black-800">{t('PDF_IMPORT.DIALOG.DROP')}</span>
                            <span className="mt-1 text-xs text-black-600">{t('PDF_IMPORT.DIALOG.LIMITS')}</span>
                        </>
                    )}
                </button>
                <input ref={input} type="file" accept="application/pdf,image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => choose(e.target.files?.[0])} />
                {error && <p className="text-sm text-red-600">{error}</p>}
                {ai?.available && !ai?.enabled ? (
                    <div className="flex flex-col gap-2">
                        <AIOptIn feature={t('PDF_IMPORT.DIALOG.AI_FEATURE')} sends={t('PDF_IMPORT.DIALOG.AI_SENDS')} onEnabled={() => refetchAi()} compact />
                        <p className="text-xs text-black-600">{t('PDF_IMPORT.DIALOG.BUILT_IN_ONLY')}</p>
                    </div>
                ) : aiUsable ? (
                    <div className="rounded-md border border-black-300 p-3">
                        <label className="flex cursor-pointer items-start gap-2 text-sm text-black-800">
                            <input type="checkbox" className="mt-0.5" checked={aiConsent} onChange={(e) => setAiConsent(e.target.checked)} />
                            <span>{t('PDF_IMPORT.DIALOG.LET_READ', { provider: ai.provider })}</span>
                        </label>
                        <p className="mt-2 text-xs text-black-600">
                            {aiConsent
                                ? t('PDF_IMPORT.DIALOG.SENT', { provider: ai.provider })
                                : t('PDF_IMPORT.DIALOG.WITHOUT')}
                        </p>
                    </div>
                ) : (
                    <p className="text-xs text-black-600">{t('PDF_IMPORT.DIALOG.NO_PROVIDER')}</p>
                )}
                <p className="text-xs text-black-600">{t('PDF_IMPORT.DIALOG.BLANK')}</p>
                <div className="flex justify-end gap-2">
                    <Button variant="v2Button" onClick={() => onOpenChange(false)}>
                        {t('PDF_IMPORT.DIALOG.CANCEL')}
                    </Button>
                    <Button onClick={submit} disabled={!file} isLoading={isLoading}>
                        {t('PDF_IMPORT.DIALOG.IMPORT')}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
