'use client';

import React, { useRef, useState } from 'react';

import { useRouter } from 'next-nprogress-bar';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useUploadOpenFormulierenImportMutation } from '@app/store/redux/open-formulieren-import-api';
import { MAX_UPLOAD_MB, uploadProblemOf, uploadTooLarge } from '@app/utils/open-formulieren-import';
import type { UploadProblem } from '@app/utils/open-formulieren-import';

import { ReportItemGroups, useImportText } from './report-items';

interface ImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    workspaceId: string;
    workspaceName: string;
}

/** Upload the zip exported from an Open Formulieren form; on success the report opens. */
export default function ImportOpenFormulierenDialog({ open, onOpenChange, workspaceId, workspaceName }: ImportDialogProps) {
    const router = useRouter();
    const text = useImportText();
    const { i18n } = useTranslation('builder');
    const input = useRef<HTMLInputElement>(null);
    const [file, setFile] = useState<File | null>(null);
    const [problem, setProblem] = useState<UploadProblem | null>(null);
    const [dragging, setDragging] = useState(false);
    const [upload, { isLoading }] = useUploadOpenFormulierenImportMutation();

    const choose = (chosen: File | undefined | null) => {
        if (!chosen) return;
        // the server checks the content; only the size is known here
        if (uploadTooLarge(chosen)) {
            setProblem({ key: 'ERROR.file_too_large', values: { mb: MAX_UPLOAD_MB }, items: [] });
            setFile(null);
            return;
        }
        setProblem(null);
        setFile(chosen);
    };

    const close = (next: boolean) => {
        if (isLoading) return;
        if (!next) {
            setFile(null);
            setProblem(null);
        }
        onOpenChange(next);
    };

    const submit = async () => {
        if (!file || isLoading) return;
        const result = await upload({ workspaceId, file });
        if ('data' in result && result.data?.id) {
            close(false);
            router.push(`/${workspaceName}/dashboard/forms/import/open-formulieren/${encodeURIComponent(result.data.id)}`);
            return;
        }
        setProblem(uploadProblemOf('error' in result ? result.error : undefined));
    };

    return (
        <Dialog open={open} onOpenChange={close}>
            <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto bg-white" title={text('DIALOG.TITLE')}>
                <DialogHeader>
                    <DialogTitle>{text('DIALOG.TITLE')}</DialogTitle>
                    <DialogDescription>{text('DIALOG.DESCRIPTION')}</DialogDescription>
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
                    aria-describedby="oof-drop-hint"
                    className={`flex h-36 w-full flex-col items-center justify-center rounded-lg border-2 border-dashed px-3 text-center text-sm transition ${dragging ? 'border-brand-500 bg-brand-100' : 'border-black-300 hover:border-brand-500'}`}
                >
                    {file ? (
                        <>
                            <span className="max-w-full font-medium break-all text-black-800">{file.name}</span>
                            <span id="oof-drop-hint" className="mt-1 text-xs text-black-600">
                                {text('DIALOG.CHOSEN', { size: new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(file.size / 1024 / 1024) })}
                            </span>
                        </>
                    ) : (
                        <>
                            <span className="font-medium text-black-800">{text('DIALOG.DROP')}</span>
                            <span id="oof-drop-hint" className="mt-1 text-xs text-black-600">
                                {text('DIALOG.DROP_HINT')}
                            </span>
                        </>
                    )}
                </button>
                <input ref={input} type="file" accept=".zip,application/zip,application/x-zip-compressed" className="hidden" tabIndex={-1} aria-hidden onChange={(e) => choose(e.target.files?.[0])} data-testid="oof-file-input" />
                <div role="alert" aria-live="assertive">
                    {problem && (
                        <div className="flex flex-col gap-3">
                            <p className="text-sm text-red-700">{text(problem.key, problem.values)}</p>
                            {problem.items.length > 0 && (
                                <div className="flex flex-col gap-2">
                                    <p className="text-sm font-medium text-black-800">{text('DIALOG.NO_ITEMS_TITLE')}</p>
                                    <div className="max-h-56 overflow-y-auto rounded-md border border-black-300 p-3">
                                        <ReportItemGroups items={problem.items} headingLevel={3} />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
                <p className="text-xs text-black-600">{text('DIALOG.KEEP')}</p>
                <div className="flex justify-end gap-2">
                    <Button variant="v2Button" onClick={() => close(false)} disabled={isLoading}>
                        {text('DIALOG.CANCEL')}
                    </Button>
                    <Button onClick={submit} disabled={!file} isLoading={isLoading}>
                        {isLoading ? text('DIALOG.IMPORTING') : text('DIALOG.IMPORT')}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
