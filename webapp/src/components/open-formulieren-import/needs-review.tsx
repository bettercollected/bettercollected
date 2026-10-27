'use client';

import React from 'react';

import Link from 'next/link';

import { TriangleAlert } from 'lucide-react';

import { useGetOpenFormulierenImportQuery } from '@app/store/redux/open-formulieren-import-api';

import { useImportText } from './report-items';

/** What an imported form's settings say about its review (api contract section 4). */
export interface ImportReviewSettings {
    needsReview?: boolean | null;
    importSource?: string | null;
    importId?: string | null;
}

/** Whether the form carries the "needs review" mark of an Open Formulieren import. */
export function needsOpenFormulierenReview(settings: ImportReviewSettings | undefined | null): boolean {
    return !!settings && settings.needsReview === true && settings.importSource === 'open_formulieren';
}

/** The mark in the forms list: shown while the imported form still needs review. */
export function NeedsReviewBadge({ settings }: { settings: ImportReviewSettings | undefined | null }) {
    const text = useImportText();
    if (!needsOpenFormulierenReview(settings)) return null;
    return <div className="mx-1 inline-block rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-900">{text('NEEDS_REVIEW')}</div>;
}

/**
 * Whether the builder shows the "needs review" banner. It follows the
 * report's own state once that has been read or changed in this session, so
 * marking the import as reviewed there removes the banner.
 */
export function useShowNeedsReviewBanner(settings: ImportReviewSettings | undefined | null, workspaceId: string | undefined): boolean {
    const marked = needsOpenFormulierenReview(settings) && !!settings?.importId;
    const { data } = useGetOpenFormulierenImportQuery({ workspaceId: workspaceId as string, importId: settings?.importId as string }, { skip: !marked || !workspaceId });
    return marked && data?.needsReview !== false;
}

/** The height the banner takes from the builder (Tailwind h-11). */
export const NEEDS_REVIEW_BANNER_HEIGHT_PX = 44;

/** A slim strip at the top of the builder for an imported form that still needs review, linking to the import report. */
export function NeedsReviewBanner({ importId, workspaceName }: { importId: string; workspaceName: string }) {
    const text = useImportText();
    return (
        <div role="status" className="flex h-11 w-full shrink-0 items-center gap-3 border-b border-amber-300 bg-amber-50 px-4 text-sm text-amber-900">
            <TriangleAlert aria-hidden className="h-4 w-4 shrink-0" />
            <span className="min-w-0 truncate">{text('BANNER.TEXT')}</span>
            <Link href={`/${workspaceName}/dashboard/forms/import/open-formulieren/${encodeURIComponent(importId)}`} className="ml-auto shrink-0 font-semibold underline underline-offset-2">
                {text('BANNER.LINK')}
            </Link>
        </div>
    );
}
