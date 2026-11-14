'use client';

/**
 * Drill-down: the responses behind one group of one card, a page at a time, each linking to the
 * response's own page (where the usual checks apply). A row holds the submission time, the form
 * version and whether the respondent was identified: no answer, name or address. A group that the
 * responses list can filter on by itself also links to that list.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';

import Link from 'next/link';

import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import { Button } from '@app/shadcn/components/ui/button';
import { useGetReportResponsesMutation } from '@app/store/workspaces/api';
import { ReportDefinition, ReportDrillRow, reportErrorOf } from '@app/utils/report';
import { responsePageUrl } from '@app/utils/response-urls';

import { ScrollBox } from './charts';

const PAGE = 25;

interface Props {
    workspaceId: string;
    workspaceName: string;
    formId: string;
    /** The definition on screen: the filters and conditions decide which responses count. */
    definition: ReportDefinition;
    cardId: string;
    group: { key: string; label: string };
    /** The responses list showing the same group, when the list can say it. */
    listHref?: string;
    onClose: () => void;
}

export default function ReportDrill({ workspaceId, workspaceName, formId, definition, cardId, group, listHref, onClose }: Props) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const [load] = useGetReportResponsesMutation();
    const [rows, setRows] = useState<ReportDrillRow[]>([]);
    const [cursor, setCursor] = useState<string | null>(null);
    const [exhausted, setExhausted] = useState(false);
    const [busy, setBusy] = useState(true);
    const [failure, setFailure] = useState<{ code?: string; status?: number } | undefined>();
    const [short, setShort] = useState(false);
    const headingRef = useRef<HTMLHeadingElement>(null);
    // an answer for a group that was replaced meanwhile is dropped
    const generation = useRef(0);
    const key = `${cardId}|${group.key}|${JSON.stringify(definition)}`;

    const fetchPage = useCallback(
        async (after: string | null, mine: number) => {
            setBusy(true);
            setFailure(undefined);
            try {
                const page = await load({ workspaceId, formId, definition, card: cardId, group: group.key, cursor: after, size: PAGE }).unwrap();
                if (generation.current !== mine) return;
                setRows((current) => (after ? [...current, ...page.responses] : page.responses));
                setCursor(page.cursor);
                setExhausted(page.exhausted);
                // a short page with a cursor: the search stopped at its budget, not at the end of the responses
                setShort(!page.exhausted && page.responses.length < PAGE);
            } catch (error) {
                if (generation.current !== mine) return;
                const found = reportErrorOf(error);
                setFailure({ code: found.code, status: found.status });
            } finally {
                if (generation.current === mine) setBusy(false);
            }
        },
        // `key` stands for the definition, card and group
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [key, workspaceId, formId, load]
    );

    useEffect(() => {
        generation.current += 1;
        setRows([]);
        setCursor(null);
        setExhausted(false);
        setShort(false);
        fetchPage(null, generation.current);
        headingRef.current?.focus();
    }, [key, fetchPage]);

    const date = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' });
    const message = failure ? (failure.status === 429 ? (failure.code === 'report_busy' ? t('REPORT.BUSY') : t('REPORT.RATE_LIMITED')) : failure.code === 'report_timeout' ? t('REPORT.TIMEOUT') : t('REPORT.ERROR')) : '';

    return (
        <section aria-labelledby="report-drill-title" className="flex flex-col gap-3 rounded border border-black-300 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <h3 id="report-drill-title" ref={headingRef} tabIndex={-1} className="m-0 text-base font-semibold text-black-900 outline-none [overflow-wrap:anywhere]">
                        {t('REPORT.DRILL_TITLE', { group: group.label })}
                    </h3>
                    <p className="m-0 text-xs text-black-600">{t('REPORT.DRILL_NOTE')}</p>
                </div>
                <button type="button" onClick={onClose} aria-label={t('REPORT.DRILL_CLOSE')} title={t('REPORT.DRILL_CLOSE')} className="-mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded text-black-700 hover:bg-black-200 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden">
                    <X aria-hidden="true" className="h-4 w-4" />
                </button>
            </div>

            {listHref && (
                <p className="m-0 text-sm">
                    <Link href={listHref} className="rounded font-medium text-brand-600 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden">
                        {t('REPORT.DRILL_LIST')}
                    </Link>
                </p>
            )}

            {failure && (
                <div role="alert" className="flex flex-col items-start gap-2">
                    <p className="m-0 text-sm text-black-900">{message}</p>
                    <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => fetchPage(cursor, generation.current)}>
                        {t('REPORT.RETRY')}
                    </Button>
                </div>
            )}

            {rows.length > 0 && (
                <ScrollBox label={t('REPORT.DRILL_TITLE', { group: group.label })}>
                    <table className="w-full border-collapse text-left text-sm">
                        <caption className="sr-only">{t('REPORT.DRILL_TITLE', { group: group.label })}</caption>
                        <thead>
                            <tr className="border-b border-black-300">
                                <th scope="col" className="py-2 pr-4 font-semibold text-black-800">
                                    {t('REPORT.DRILL_SUBMITTED')}
                                </th>
                                <th scope="col" className="px-2 py-2 font-semibold text-black-800">
                                    {t('REPORT.DRILL_VERSION')}
                                </th>
                                <th scope="col" className="px-2 py-2 font-semibold text-black-800">
                                    {t('REPORT.DRILL_RESPONDENT')}
                                </th>
                                <th scope="col" className="py-2 pl-2">
                                    <span className="sr-only">{t('REPORT.DRILL_OPEN')}</span>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((row) => {
                                const when = row.submittedAt ? date.format(new Date(row.submittedAt)) : '–';
                                return (
                                    <tr key={row.id} className="border-b border-black-200 last:border-0">
                                        <th scope="row" className="py-2 pr-4 font-normal text-black-900 tabular-nums">
                                            {when}
                                        </th>
                                        <td className="px-2 py-2 text-black-900 tabular-nums">{row.formVersion ?? '–'}</td>
                                        <td className="px-2 py-2 text-black-900">{t(`REPORT.GROUP.${row.respondent}`)}</td>
                                        <td className="py-1 pl-2 text-right">
                                            <Link
                                                href={responsePageUrl(workspaceName, formId, row.id)}
                                                aria-label={t('REPORT.DRILL_OPEN_ONE', { when })}
                                                className="inline-flex min-h-9 items-center rounded px-1 font-medium text-brand-600 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                                            >
                                                {t('REPORT.DRILL_OPEN')}
                                            </Link>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </ScrollBox>
            )}

            <p role="status" aria-live="polite" className="m-0 text-sm text-black-700">
                {busy ? t('REPORT.LOADING') : rows.length === 0 && exhausted ? t('REPORT.DRILL_NONE') : rows.length > 0 ? t('REPORT.DRILL_SHOWN', { count: rows.length }) : ''}
                {!busy && short && ` ${t('REPORT.DRILL_BUDGET')}`}
            </p>

            {!exhausted && cursor && !busy && !failure && (
                <div>
                    <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => fetchPage(cursor, generation.current)}>
                        {t('REPORT.DRILL_MORE')}
                    </Button>
                </div>
            )}
        </section>
    );
}
