'use client';

/**
 * One card of a report: a figure with its caption (title and how many answered),
 * the chart that suits it, a switch to read the same figures as a table, and the
 * buttons that change, move or remove it. Colour is never the only carrier: the
 * values are printed, and the table is always one press away.
 */
import React, { useEffect, useId, useRef, useState } from 'react';

import { ArrowDown, ArrowUp, BarChart3, Download, Pencil, Table2, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import { cn } from '@app/shadcn/util/lib';
import { ReportCardDef, ReportCardResult, ReportCatalogue, cardProblem } from '@app/utils/report';
import { ReportRow, buildCardView, cardTitle, chartSummary } from '@app/utils/report-view';

import { BarChart, DataTable, DonutChart, LineChart, TileChart } from './charts';
import ReportCardEditor from './report-card-editor';

const iconButton = 'inline-flex h-9 w-9 items-center justify-center rounded text-black-700 hover:bg-black-200 hover:text-black-900 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden disabled:opacity-40 disabled:hover:bg-transparent';

interface Props {
    def: ReportCardDef;
    result?: ReportCardResult;
    catalogue: ReportCatalogue;
    /** The figures are on their way (first load or a new definition). */
    loading?: boolean;
    first: boolean;
    last: boolean;
    onChange: (card: ReportCardDef) => void;
    onRemove: () => void;
    onMove: (delta: -1 | 1) => void;
    /** Open the responses behind a group of this card (offered in the table, for a card with groups the pass can tell). */
    onDrill?: (card: ReportCardDef, row: ReportRow) => void;
    /**
     * Download this card's table as a CSV. Given only to a member who may export responses (the server asks for
     * `response.export` too); resolves to the locale key of what went wrong, or nothing once the file was handed over.
     */
    onDownload?: (card: ReportCardDef) => Promise<string | undefined>;
}

export default function ReportCard({ def, result, catalogue, loading, first, last, onChange, onRemove, onMove, onDrill, onDownload }: Props) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const id = useId().replace(/:/g, '');
    const [asTable, setAsTable] = useState(false);
    const [editing, setEditing] = useState(false);
    const [download, setDownload] = useState<{ phase: 'idle' | 'busy' | 'done' | 'error'; key?: string }>({ phase: 'idle' });
    const mounted = useRef(true);
    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
        };
    }, []);
    // a changed card has other figures: what was said of the last file is no longer about it
    const shape = JSON.stringify(def);
    useEffect(() => setDownload({ phase: 'idle' }), [shape]);
    const problem = cardProblem(def, catalogue);
    const view = buildCardView(def, result, catalogue, t, locale);
    const title = cardTitle(def, catalogue, t);
    const summaryId = `${id}-summary`;
    const label = t('REPORT.A11Y_CHART', { title });
    const isTile = view.kind === 'tile';
    const isLine = view.kind === 'line';
    const wide = isLine || view.kind === 'table';
    const ready = !problem && !!result && !view.empty;
    const showTable = view.kind === 'table' || asTable;
    // a group's responses are found by the pass: a deletion-request or feedback status is not read by it
    const drillable = !!onDrill && !!def.dimension && !['status', 'feedback_status'].includes(def.dimension.field);

    const runDownload = async () => {
        if (!onDownload || download.phase === 'busy') return;
        setDownload({ phase: 'busy' });
        const problemKey = await onDownload(def);
        if (mounted.current) setDownload(problemKey ? { phase: 'error', key: problemKey } : { phase: 'done' });
    };

    const chart = !ready ? null : view.kind === 'tile' ? (
        <TileChart view={view} summaryId={summaryId} label={label} locale={locale} />
    ) : view.kind === 'donut' ? (
        <DonutChart view={view} summaryId={summaryId} label={label} locale={locale} />
    ) : view.kind === 'line' ? (
        <LineChart view={view} summaryId={summaryId} label={label} locale={locale} />
    ) : (
        <BarChart view={view} summaryId={summaryId} label={label} locale={locale} />
    );

    return (
        <figure aria-labelledby={`${id}-title`} className={cn('report-viz m-0 flex min-w-0 flex-col gap-3 rounded border border-black-300 bg-white p-4', isTile ? 'md:col-span-2' : wide ? 'md:col-span-6' : 'md:col-span-3')}>
            <figcaption className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                <div className="min-w-0">
                    <span id={`${id}-title`} className="block text-sm leading-snug font-semibold text-black-900 [overflow-wrap:anywhere]">
                        {title}
                    </span>
                    {ready && <span className="block text-xs leading-snug text-black-600">{view.basis}</span>}
                </div>
                <div className="-mr-1.5 flex shrink-0 items-center">
                    <button type="button" className={iconButton} aria-label={t('REPORT.CHANGE_CARD', { title })} title={t('REPORT.CHANGE')} aria-expanded={editing} onClick={() => setEditing((value) => !value)}>
                        <Pencil aria-hidden="true" className="h-4 w-4" />
                    </button>
                    <button type="button" className={iconButton} aria-label={t('REPORT.MOVE_UP_CARD', { title })} title={t('REPORT.MOVE_UP')} disabled={first} onClick={() => onMove(-1)}>
                        <ArrowUp aria-hidden="true" className="h-4 w-4" />
                    </button>
                    <button type="button" className={iconButton} aria-label={t('REPORT.MOVE_DOWN_CARD', { title })} title={t('REPORT.MOVE_DOWN')} disabled={last} onClick={() => onMove(1)}>
                        <ArrowDown aria-hidden="true" className="h-4 w-4" />
                    </button>
                    <button type="button" className={iconButton} aria-label={t('REPORT.REMOVE_CARD', { title })} title={t('REPORT.REMOVE')} onClick={onRemove}>
                        <Trash2 aria-hidden="true" className="h-4 w-4" />
                    </button>
                </div>
            </figcaption>

            {editing && (
                <ReportCardEditor
                    initial={def}
                    catalogue={catalogue}
                    applyLabel={t('REPORT.DONE')}
                    onCancel={() => setEditing(false)}
                    onApply={(card) => {
                        setEditing(false);
                        setAsTable(false);
                        onChange(card);
                    }}
                />
            )}

            {problem ? (
                <p role="status" className="m-0 text-sm text-black-700">
                    {problem === 'unknown' ? t('REPORT.UNAVAILABLE_FIELD') : t('REPORT.INVALID_CARD')}
                </p>
            ) : !result ? (
                <p className="m-0 text-sm text-black-600">{loading ? t('REPORT.LOADING') : ''}</p>
            ) : view.empty ? (
                <p className="m-0 text-sm text-black-700">{t('REPORT.NO_ANSWERS')}</p>
            ) : (
                <>
                    {showTable ? (
                        <DataTable view={view} caption={title} onOpen={drillable ? (row) => onDrill?.(def, row) : undefined} />
                    ) : (
                        <>
                            <p id={summaryId} className="sr-only">
                                {chartSummary(view, t)}
                            </p>
                            {chart}
                            <DataTable view={view} caption={title} srOnly />
                        </>
                    )}
                    {(view.multiple || view.truncated) && (
                        <p className="m-0 text-xs leading-snug text-black-600">
                            {view.multiple && <span className="block">{t('REPORT.MULTI_NOTE')}</span>}
                            {view.truncated && <span className="block">{t('REPORT.TRUNCATED')}</span>}
                        </p>
                    )}
                    {(view.kind !== 'table' || !!onDownload) && (
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                            {view.kind !== 'table' && (
                                <button
                                    type="button"
                                    onClick={() => setAsTable((value) => !value)}
                                    className="inline-flex min-h-9 items-center gap-1.5 rounded px-1 text-sm font-medium text-brand-600 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                                >
                                    {asTable ? <BarChart3 aria-hidden="true" className="h-4 w-4" /> : <Table2 aria-hidden="true" className="h-4 w-4" />}
                                    {asTable ? t('REPORT.SHOW_CHART') : t('REPORT.SHOW_TABLE')}
                                </button>
                            )}
                            {onDownload && (
                                <button
                                    type="button"
                                    onClick={runDownload}
                                    disabled={download.phase === 'busy'}
                                    className="inline-flex min-h-9 items-center gap-1.5 rounded px-1 text-sm font-medium text-brand-600 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden disabled:opacity-60 disabled:hover:no-underline"
                                >
                                    <Download aria-hidden="true" className="h-4 w-4" />
                                    {t('REPORT.EXPORT')}
                                    {/* the visible words come first in the name; which card it is is said after them */}
                                    <span className="sr-only">: {title}</span>
                                </button>
                            )}
                        </div>
                    )}
                    {onDownload && download.phase !== 'idle' && (
                        <p role="status" className="m-0 text-xs leading-snug text-black-700">
                            {download.phase === 'busy' ? t('REPORT.EXPORT_BUSY') : download.phase === 'done' ? t('REPORT.EXPORT_DONE') : t(download.key ?? 'REPORT.EXPORT_ERROR')}
                        </p>
                    )}
                </>
            )}
        </figure>
    );
}
