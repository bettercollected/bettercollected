'use client';

import React from 'react';

import Link from 'next/link';

import { ShieldAlert } from 'lucide-react';

import { Button, buttonClassName } from '@app/shadcn/components/ui/button';
import { useGetOpenFormulierenImportQuery, useReviewOpenFormulierenImportMutation } from '@app/store/redux/open-formulieren-import-api';
import type { OpenFormulierenImport } from '@app/store/redux/open-formulieren-import-api';
import { nationalIdentityItems, plainText, reportLabelOf } from '@app/utils/open-formulieren-import';

import { ReportItemGroups, useImportText } from './report-items';

const MAX_ID_LABELS = 5;

/** The prominent flag: the import found questions asking for a national identity number. */
function NationalIdentityFlag({ data }: { data: OpenFormulierenImport }) {
    const text = useImportText();
    const flagged = nationalIdentityItems(data.report?.items ?? []);
    if (flagged.length === 0) return null;
    const labels = flagged
        .map((item) => reportLabelOf(item))
        .filter(Boolean)
        .slice(0, MAX_ID_LABELS);
    const more = flagged.length - labels.length;
    return (
        <section aria-labelledby="oof-id-flag" className="flex gap-3 rounded-md border border-amber-400 bg-amber-50 p-4 text-amber-900">
            <ShieldAlert aria-hidden className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="min-w-0">
                <h2 id="oof-id-flag" className="text-base font-semibold">
                    {text('REPORT.ID_TITLE')}
                </h2>
                <p className="mt-1 text-sm">{text('REPORT.ID_BODY')}</p>
                {labels.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-sm">
                        {labels.map((label, index) => (
                            <li key={`${label}-${index}`} className="break-words">
                                {label}
                            </li>
                        ))}
                        {more > 0 && <li>{text('REPORT.ID_MORE', { count: more })}</li>}
                    </ul>
                )}
            </div>
        </section>
    );
}

function Summary({ data }: { data: OpenFormulierenImport }) {
    const text = useImportText();
    const s = data.summary;
    const cells: Array<{ key: string; label: string; warn?: boolean }> = [
        { key: 'pages', label: text('REPORT.PAGES', { count: s?.pages ?? 0 }) },
        { key: 'fields', label: text('REPORT.QUESTIONS', { count: s?.fields ?? 0 }) },
        { key: 'rules', label: text('REPORT.RULES', { count: s?.logicRules ?? 0 }) },
        { key: 'dropped', label: text('REPORT.DROPPED', { count: s?.dropped ?? 0 }), warn: (s?.dropped ?? 0) > 0 },
        { key: 'flagged', label: text('REPORT.FLAGGED', { count: s?.flagged ?? 0 }), warn: (s?.flagged ?? 0) > 0 }
    ];
    return (
        <section aria-label={text('REPORT.SUMMARY_LABEL')}>
            <ul className="flex flex-wrap gap-2">
                {cells.map((cell) => (
                    <li key={cell.key} className={`rounded border px-3 py-1.5 text-sm ${cell.warn ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-black-300 bg-white text-black-800'}`}>
                        {cell.label}
                    </li>
                ))}
            </ul>
        </section>
    );
}

/**
 * The import report: what was imported, what was left out or changed, and the
 * national identity number flag. Reached after an upload and, later, from the
 * builder's "needs review" banner.
 */
export function ImportReportView({ data, workspaceId, workspaceName }: { data: OpenFormulierenImport; workspaceId: string; workspaceName: string }) {
    const text = useImportText();
    const [review, { isLoading, isSuccess, isError, originalArgs }] = useReviewOpenFormulierenImportMutation();
    const items = data.report?.items ?? [];
    const name = plainText(data.fileName, 120);
    const version = plainText(data.sourceVersion, 40);
    const editorUrl = `/${workspaceName}/dashboard/forms/${encodeURIComponent(data.formId)}/edit`;
    const setReviewed = (reviewed: boolean) => review({ workspaceId, importId: data.id, reviewed });

    return (
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-5 py-8 md:px-10">
            <header>
                <h1 className="h3-new text-black-800">{text('REPORT.TITLE')}</h1>
                {name && <p className="mt-1 text-sm break-words text-black-600">{version ? text('REPORT.FROM_VERSION', { name, version }) : text('REPORT.FROM', { name })}</p>}
            </header>

            <NationalIdentityFlag data={data} />
            <Summary data={data} />

            <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-3">
                    <Link href={editorUrl} className={buttonClassName({ variant: 'primary', size: 'sm' })}>
                        {text('REPORT.OPEN_EDITOR')}
                    </Link>
                    {data.needsReview ? (
                        <Button variant="v2Button" onClick={() => setReviewed(true)} isLoading={isLoading}>
                            {text('REPORT.MARK_REVIEWED')}
                        </Button>
                    ) : (
                        <Button variant="v2Button" onClick={() => setReviewed(false)} isLoading={isLoading}>
                            {text('REPORT.MARK_REVIEW_AGAIN')}
                        </Button>
                    )}
                </div>
                <p className="text-sm text-black-700">{data.needsReview ? text('REPORT.NEEDS_REVIEW_NOTE') : text('REPORT.REVIEWED_NOTE')}</p>
                <p role="status" aria-live="polite" className={`text-sm ${isError ? 'text-red-700' : 'text-black-700'}`}>
                    {isError ? text('REPORT.REVIEW_FAILED') : isSuccess ? (originalArgs?.reviewed ? text('REPORT.REVIEW_SAVED') : text('REPORT.REVIEW_AGAIN_SAVED')) : ''}
                </p>
            </div>

            {items.length === 0 ? <p className="text-sm text-black-700">{text('REPORT.ALL_CLEAR')}</p> : <ReportItemGroups items={items} />}
            {data.report?.truncated && <p className="text-xs text-black-600">{text('REPORT.TRUNCATED')}</p>}
        </div>
    );
}

/** Loads the report of an import and shows it. */
export default function ImportReport({ workspaceId, workspaceName, importId }: { workspaceId: string; workspaceName: string; importId: string }) {
    const text = useImportText();
    const { data, isError, isLoading, error } = useGetOpenFormulierenImportQuery({ workspaceId, importId }, { skip: !workspaceId });
    // reading a report needs the form-edit permission; a 403 says so, a 404 says it is gone
    const loadFailureText = (status?: number) => (status === 404 ? text('ERROR.import_not_found') : status === 403 ? text('REPORT.FORBIDDEN') : text('REPORT.LOAD_FAILED'));
    if (data) return <ImportReportView data={data} workspaceId={workspaceId} workspaceName={workspaceName} />;
    if (isError) {
        return (
            <p role="alert" className="mx-auto max-w-3xl p-10 text-sm text-red-700">
                {loadFailureText((error as { status?: number } | undefined)?.status)}
            </p>
        );
    }
    return (
        <p role="status" className="mx-auto max-w-3xl p-10 text-sm text-black-600">
            {isLoading || !workspaceId ? text('REPORT.LOADING') : ''}
        </p>
    );
}
