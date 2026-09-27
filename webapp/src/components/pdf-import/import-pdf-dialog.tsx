'use client';

import React, { useRef, useState } from 'react';

import { useRouter } from 'next-nprogress-bar';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useStartPdfImportMutation } from '@app/store/redux/pdf-import-api';
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

    const choose = (chosen: File | undefined | null) => {
        if (!chosen) return;
        const problem = validateUpload(chosen);
        setError(problem);
        setFile(problem ? null : chosen);
    };

    const submit = async () => {
        if (!file) return;
        const result: any = await startImport({ workspaceId, file });
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
            <DialogContent className="max-w-lg bg-white">
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
                <p className="text-xs text-black-600">Only the questions are imported, never what someone has filled in. Page images are read by your workspace&apos;s AI provider. The file is kept with the draft form until you delete the form.</p>
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
