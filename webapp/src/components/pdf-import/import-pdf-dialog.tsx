'use client';

import React, { useRef, useState } from 'react';

import { useRouter } from 'next-nprogress-bar';

import { AIOptIn } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useGetPdfImportAiQuery, useStartPdfImportMutation } from '@app/store/redux/pdf-import-api';
import { validateUpload } from '@app/utils/pdf-import';

interface ImportPdfDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    workspaceId: string;
    workspaceName: string;
}

/** Upload a PDF (or a photo of a paper form) and follow its import. */
export default function ImportPdfDialog({ open, onOpenChange, workspaceId, workspaceName }: ImportPdfDialogProps) {
    const router = useRouter();
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
        setError(detail?.message || (typeof detail === 'string' ? detail : null) || 'The upload failed. Please try again.');
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg bg-white" title="Import a PDF form">
                <DialogHeader>
                    <DialogTitle>Import a PDF form</DialogTitle>
                    <DialogDescription>Upload a fillable or printed PDF, or a photo of a paper form. We turn it into a draft form you can review and edit before publishing.</DialogDescription>
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
                            <span className="mt-1 text-xs text-black-600">{(file.size / 1024 / 1024).toFixed(1)} MB · click to choose another file</span>
                        </>
                    ) : (
                        <>
                            <span className="font-medium text-black-800">Drop a file here, or click to choose</span>
                            <span className="mt-1 text-xs text-black-600">PDF, PNG, JPEG or WebP · up to 15 MB and 30 pages</span>
                        </>
                    )}
                </button>
                <input ref={input} type="file" accept="application/pdf,image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => choose(e.target.files?.[0])} />
                {error && <p className="text-sm text-red-600">{error}</p>}
                {ai?.available && !ai?.enabled ? (
                    <div className="flex flex-col gap-2">
                        <AIOptIn feature="PDF import" sends="the page text and page images of a file, only when you also agree for that upload" onEnabled={() => refetchAi()} compact />
                        <p className="text-xs text-black-600">Until then, the import uses the built-in reader only. The draft may need more manual review.</p>
                    </div>
                ) : aiUsable ? (
                    <div className="rounded-md border border-black-200 p-3">
                        <label className="flex cursor-pointer items-start gap-2 text-sm text-black-800">
                            <input type="checkbox" className="mt-0.5" checked={aiConsent} onChange={(e) => setAiConsent(e.target.checked)} />
                            <span>Let {ai.provider} read this document to recognise the questions</span>
                        </label>
                        <p className="mt-2 text-xs text-black-600">
                            {aiConsent
                                ? `The page text and page images of this file are sent to ${ai.provider} to recognise its questions. On a filled-in form, the answers written on it are visible to ${ai.provider} in the page images. Don't upload forms that hold other people's personal data unless you're allowed to share it.`
                                : 'Without this, the import uses the built-in reader only. The draft may need more manual review.'}
                        </p>
                    </div>
                ) : (
                    <p className="text-xs text-black-600">No AI provider is set up on this server, so the import uses the built-in reader only. The draft may need more manual review.</p>
                )}
                <p className="text-xs text-black-600">Upload a blank form if you can. The file is kept with the draft form until you delete the form.</p>
                <div className="flex justify-end gap-2">
                    <Button variant="v2Button" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={submit} disabled={!file} isLoading={isLoading}>
                        Import
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
