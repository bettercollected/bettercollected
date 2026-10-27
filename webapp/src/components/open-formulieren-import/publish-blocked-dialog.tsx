'use client';

import React from 'react';

import Link from 'next/link';

import { Button, buttonClassName } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@app/shadcn/components/ui/dialog';
import { useGetOpenFormulierenImportQuery, useReviewOpenFormulierenImportMutation } from '@app/store/redux/open-formulieren-import-api';
import { REPORT_REMOVED } from '@app/utils/open-formulieren-import';

import { useImportText } from './report-items';

/** The address of an import's report page. */
export function importReportPath(workspaceName: string, importId: string) {
    return `/${workspaceName}/dashboard/forms/import/open-formulieren/${encodeURIComponent(importId)}`;
}

/**
 * Shown when publishing is refused because the form is an import that still
 * needs review (the server's `needs_review` publish problem, or the mark the
 * form already carries). Links to the import report and clears the mark in
 * place; once it is clear, offers to publish.
 */
export function PublishBlockedByReviewDialog({ open, importId, workspaceId, workspaceName, onClose, onPublish }: { open: boolean; importId: string; workspaceId: string; workspaceName: string; onClose: () => void; onPublish: () => void }) {
    const text = useImportText();
    const [review, { isLoading, isSuccess, isError, reset }] = useReviewOpenFormulierenImportMutation();
    // the report may be out of reach (the import is switched off, or it was deleted with the form it was made for):
    // the mark can be cleared all the same, only the link to the report goes
    const report = useGetOpenFormulierenImportQuery({ workspaceId, importId }, { skip: !open || !importId || !workspaceId });
    const reportAvailable = !!report.data && report.data.status !== REPORT_REMOVED;
    const reportOutOfReach = report.isError || report.data?.status === REPORT_REMOVED;
    const close = () => {
        reset();
        onClose();
    };
    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && close()}>
            <DialogContent className="max-w-lg" title={text('PUBLISH_BLOCKED.TITLE')}>
                <DialogHeader>
                    <div aria-hidden="true" className="text-lg leading-none font-semibold tracking-tight">
                        {text('PUBLISH_BLOCKED.TITLE')}
                    </div>
                    <DialogDescription>{text(reportOutOfReach ? 'PUBLISH_BLOCKED.TEXT_NO_REPORT' : 'PUBLISH_BLOCKED.TEXT')}</DialogDescription>
                </DialogHeader>
                <p role="status" aria-live="polite" className={`text-sm ${isError ? 'text-red-700' : 'text-black-700'}`}>
                    {isError ? text('PUBLISH_BLOCKED.FAILED') : isSuccess ? text('PUBLISH_BLOCKED.CLEARED') : ''}
                </p>
                <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="secondary" onClick={close}>
                        {text('PUBLISH_BLOCKED.CLOSE')}
                    </Button>
                    {isSuccess ? (
                        <Button
                            onClick={() => {
                                close();
                                onPublish();
                            }}
                            className="text-white"
                        >
                            {text('PUBLISH_BLOCKED.PUBLISH')}
                        </Button>
                    ) : (
                        <>
                            {reportAvailable && (
                                <Link href={importReportPath(workspaceName, importId)} className={buttonClassName({ variant: 'v2Button', size: 'sm' })}>
                                    {text('PUBLISH_BLOCKED.OPEN_REPORT')}
                                </Link>
                            )}
                            <Button onClick={() => review({ workspaceId, importId, reviewed: true })} isLoading={isLoading} className="text-white">
                                {text('PUBLISH_BLOCKED.MARK_REVIEWED')}
                            </Button>
                        </>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
