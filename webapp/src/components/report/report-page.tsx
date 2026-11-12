'use client';

/**
 * Responses › Report: counts, averages and distributions of a form's answers
 * (docs/reporting.md). The report is a definition (filters and cards) that lives
 * in the address: the responses list's own filters, and the cards once the viewer
 * has changed them. Until then it is the Overview, computed from the form's
 * questions and never stored. One request asks for every card.
 *
 * Shown only while the server has reports on (`reportingEnabled`) and to a
 * member who holds `response.read` and `analytics.read`; anything else is the
 * page of a form that has no such section.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import ResponseFilters from '@app/components/datatable/response-filters';
import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { selectForm } from '@app/store/forms/slice';
import { useGetReportFieldsQuery, useGetReportViewsQuery, useQueryReportQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { OVERVIEW_QUESTIONS, ReportCardDef, ReportCardResult, ReportError, ReportView, cardsParam, isTimeDimension, overviewCards, parseCardsParam, reportDefinition, reportErrorOf, reportFilters, viewerZone, cardProblem } from '@app/utils/report';
import { VIEW_ID, cardsOf, filtersOf, isModified } from '@app/utils/report-views';
import { DEFAULT_STATE, ResponseListState, localDayStart, parseResponseListState, responseListSearchParams } from '@app/utils/response-list-state';

import ReportCard from './report-card';
import ReportCardEditor, { blankCard } from './report-card-editor';
import ReportViews from './report-views';

/** The viewer's calendar day `days` days before today, as `YYYY-MM-DD`. */
export function daysAgo(days: number, now = new Date()): string {
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - days);
    return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
}

/** The filters of a state, without page, size or sort: what the report carries from the list. */
export function filterState(state: ResponseListState): ResponseListState {
    return { ...DEFAULT_STATE, from: state.from, to: state.to, status: state.status, who: state.who, version: state.version };
}

function ErrorPanel({ error, onRetry, onNarrow, currentVersion }: { error: ReportError; onRetry: () => void; onNarrow: (changes: Partial<ResponseListState>) => void; currentVersion?: number }) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    if (error.code === 'too_many_rows') {
        const format = (value: number) => new Intl.NumberFormat(locale).format(value);
        return (
            <div role="alert" className="flex flex-col gap-3 rounded border border-black-300 bg-white p-4">
                <p className="m-0 text-sm text-black-900">{t('REPORT.TOO_MANY', { rows: format(error.count ?? 0), max: format(error.max ?? 20000) })}</p>
                <p className="m-0 text-sm text-black-700">{t('REPORT.TOO_MANY_HELP')}</p>
                <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => onNarrow({ from: daysAgo(30), to: undefined })}>
                        {t('REPORT.NARROW_30_DAYS')}
                    </Button>
                    {currentVersion !== undefined && (
                        <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => onNarrow({ version: currentVersion })}>
                            {t('REPORT.NARROW_VERSION', { n: currentVersion })}
                        </Button>
                    )}
                </div>
            </div>
        );
    }
    const message = error.code === 'rate_limited' || error.status === 429 ? (error.code === 'report_busy' ? t('REPORT.BUSY') : t('REPORT.RATE_LIMITED')) : error.code === 'report_busy' ? t('REPORT.BUSY') : error.code === 'report_timeout' ? t('REPORT.TIMEOUT') : t('REPORT.ERROR');
    return (
        <div role="alert" className="flex flex-col items-start gap-3 rounded border border-black-300 bg-white p-4">
            <p className="m-0 text-sm text-black-900">{message}</p>
            <Button type="button" variant="v2Button" className="h-10 px-4" onClick={onRetry}>
                {t('REPORT.RETRY')}
            </Button>
        </div>
    );
}

export default function ReportPage() {
    const { t } = useTranslation();
    const router = useRouter();
    const pathname = usePathname() ?? '';
    const searchParams = useSearchParams();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { can, reportingEnabled, ready } = useWorkspacePermissions();
    const allowed = !!reportingEnabled && can(WorkspacePermission.RESPONSE_READ) && can(WorkspacePermission.ANALYTICS_READ);
    const workspaceId: string | undefined = workspace?.id;
    const formId: string | undefined = form?.formId;
    const [adding, setAdding] = useState(false);
    const headingRef = useRef<HTMLHeadingElement>(null);
    const addRef = useRef<HTMLButtonElement>(null);
    const filtersToggleRef = useRef<HTMLButtonElement>(null);

    const params = searchParams ?? new URLSearchParams();
    const listState = useMemo(() => filterState(parseResponseListState(params)), [params]);
    const urlCards = useMemo(() => parseCardsParam(params.get('cards')), [params]);
    const all = params.get('all') === '1';
    const viewParam = params.get('view');
    const viewId = viewParam && VIEW_ID.test(viewParam) ? viewParam : undefined;
    const tz = useMemo(() => viewerZone(), []);

    const { data: catalogue, isLoading: catalogueLoading, error: catalogueError, refetch: refetchCatalogue } = useGetReportFieldsQuery({ workspaceId: workspaceId as string, formId: formId as string }, { skip: !allowed || !workspaceId || !formId });
    const cards: ReportCardDef[] = useMemo(() => (catalogue ? (urlCards ?? overviewCards(catalogue, all)) : []), [catalogue, urlCards, all]);
    const { data: viewList, isLoading: viewsLoading, isError: viewsFailed, refetch: refetchViews } = useGetReportViewsQuery({ workspaceId: workspaceId as string, formId: formId as string }, { skip: !allowed || !workspaceId || !formId });
    const currentView = viewList?.views.find((view) => view.id === viewId);
    // a card the form can no longer answer is shown with its reason and left out of the request
    const asked = useMemo(() => (catalogue ? cards.filter((card) => !cardProblem(card, catalogue)) : []), [cards, catalogue]);
    const definition = useMemo(() => reportDefinition(asked, reportFilters(listState, localDayStart), tz), [asked, listState, tz]);
    const {
        // the figures of THIS definition only: an edited card never shows its old figures under its new labels
        currentData: result,
        error: queryError,
        isFetching,
        isError,
        refetch
    } = useQueryReportQuery({ workspaceId: workspaceId as string, formId: formId as string, definition }, {
            skip: !allowed || !workspaceId || !formId || !catalogue || asked.length === 0,
            // a pass reads up to 20,000 responses and counts against the rate limit and the replicas' places: no pass because a tab got focus
            refetchOnFocus: false,
            refetchOnReconnect: false
        }
    );
    const error = isError ? reportErrorOf(queryError) : undefined;

    const write = useCallback(
        (changes: { state?: ResponseListState; cards?: ReportCardDef[] | null; all?: boolean; view?: string | null }, replace = false) => {
            const state = changes.state ?? listState;
            const next = responseListSearchParams(filterState(state));
            const nextCards = changes.cards === undefined ? urlCards : (changes.cards ?? undefined);
            if (nextCards) next.set('cards', cardsParam(nextCards));
            if (changes.all ?? (all && !nextCards)) next.set('all', '1');
            const nextView = changes.view === undefined ? viewId : (changes.view ?? undefined);
            if (nextView) next.set('view', nextView);
            const query = next.toString();
            const url = query ? `${pathname}?${query}` : pathname;
            if (replace) router.replace(url, { scroll: false });
            else router.push(url, { scroll: false });
        },
        [all, listState, pathname, router, urlCards, viewId]
    );
    const filterChange = useCallback((changes: Partial<ResponseListState>) => write({ state: { ...listState, ...changes } }), [listState, write]);
    const clearFilters = useCallback(() => write({ state: { ...DEFAULT_STATE } }), [write]);

    const setCards = (next: ReportCardDef[]) => write({ cards: next }, true);
    // a saved view: its filters and cards become the report in the address; no view is the Overview (the filters stay)
    const openView = (view: ReportView | null) => (view ? write({ state: { ...DEFAULT_STATE, ...filtersOf(view.definition) }, cards: cardsOf(view.definition), view: view.id }) : write({ cards: null, view: null }));
    const markView = (view: ReportView | null) => write({ view: view ? view.id : null }, true);
    const change = (index: number, card: ReportCardDef) => setCards(cards.map((existing, at) => (at === index ? card : existing)));
    const remove = (index: number) => {
        setCards(cards.filter((_, at) => at !== index));
        headingRef.current?.focus();
    };
    const move = (index: number, delta: -1 | 1) => {
        const next = [...cards];
        [next[index], next[index + delta]] = [next[index + delta], next[index]];
        setCards(next);
    };

    // the live region says when figures are on their way and when they have arrived
    const [announce, setAnnounce] = useState('');
    useEffect(() => {
        if (isFetching) setAnnounce(t('REPORT.UPDATING'));
        else if (result && !isError) setAnnounce(t('REPORT.UPDATED', { count: result.n }));
    }, [isFetching, result, isError, t]);

    if (!ready) return <p role="status">{t('REPORT.LOADING')}</p>;
    if (!allowed) {
        return (
            <p role="status" className="text-sm text-black-700">
                {t('REPORT.OFF')}
            </p>
        );
    }

    const listHref = `${pathname.replace(/\/report\/?$/, '')}${responseListSearchParams(listState).toString() ? `?${responseListSearchParams(listState).toString()}` : ''}`;
    const modified = !!currentView && !!catalogue && isModified(currentView, cards, reportFilters(listState, localDayStart));
    // an address that names a view the member cannot open (deleted, or someone else's private one)
    const viewMissing = !!viewId && !!viewList && !currentView;
    const filtersActive = !!(listState.from || listState.to || listState.status || listState.who || listState.version);
    const empty = !!result && !isError && result.n === 0;
    const hasTime = !!catalogue && cards.some((card) => card.dimension && isTimeDimension(catalogue, card.dimension.field));
    const catalogueFailure = catalogueError ? reportErrorOf(catalogueError) : undefined;
    const resultById = new Map<string, ReportCardResult>((result?.cards ?? []).map((card) => [card.id, card]));
    const questionCount = catalogue?.fields.length ?? 0;

    return (
        <div className="flex flex-col gap-4">
            <nav aria-label={t('REPORT.BREADCRUMB')}>
                <ol className="m-0 flex list-none items-center gap-1.5 p-0 text-sm text-black-700">
                    <li>
                        <Link href={listHref} className="rounded text-brand-600 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden">
                            {t('FORM_SHELL.RESPONSES_TAB')}
                        </Link>
                    </li>
                    <li aria-hidden="true">›</li>
                    <li aria-current="page">{t('REPORT.TITLE')}</li>
                </ol>
            </nav>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                    <h2 ref={headingRef} tabIndex={-1} className="m-0 text-xl font-semibold text-black-900 outline-none">
                        {t('REPORT.TITLE')}
                    </h2>
                    <p className="m-0 mt-1 max-w-2xl text-sm text-black-700">{t('REPORT.INTRO')}</p>
                </div>
            </div>

            {catalogue && (
                <ReportViews
                    workspaceId={workspaceId as string}
                    formId={formId as string}
                    list={viewList}
                    loading={viewsLoading}
                    failed={viewsFailed}
                    current={currentView}
                    modified={modified}
                    definition={definition}
                    canSave={asked.length > 0}
                    onOpen={openView}
                    onMark={markView}
                    onReload={() => refetchViews()}
                />
            )}
            {viewMissing && (
                <p role="status" className="m-0 text-sm text-black-700">
                    {t('REPORT.VIEW_MISSING')}
                </p>
            )}

            <ResponseFilters toggleRef={filtersToggleRef} state={listState} currentVersion={form?.version} onChange={filterChange} onClear={clearFilters} hideSort />

            <p role="status" aria-live="polite" data-testid="report-live" className="sr-only">
                {announce}
            </p>

            {catalogueLoading ? (
                <p className="m-0 text-sm text-black-600">{t('REPORT.LOADING')}</p>
            ) : catalogueFailure ? (
                <ErrorPanel error={catalogueFailure.code === 'reporting_off' ? { code: 'reporting_off' } : catalogueFailure} onRetry={() => refetchCatalogue()} onNarrow={filterChange} />
            ) : catalogue && error ? (
                <ErrorPanel error={error} onRetry={() => refetch()} onNarrow={filterChange} currentVersion={form?.version} />
            ) : catalogue ? (
                <>
                    {result?.notices.includes('unreadable_answers') && (
                        <p role="status" className="m-0 rounded border border-black-300 bg-white p-3 text-sm text-black-800">
                            {t('REPORT.UNREADABLE')}
                        </p>
                    )}
                    {empty ? (
                        <div role="status" className="flex flex-col gap-1 rounded border border-black-300 bg-white p-6">
                            <p className="m-0 text-base font-semibold text-black-900">{filtersActive ? t('REPORT.EMPTY_FILTERED') : t('REPORT.EMPTY_FORM_TITLE')}</p>
                            {!filtersActive && <p className="m-0 text-sm text-black-700">{t('REPORT.EMPTY_FORM')}</p>}
                        </div>
                    ) : (
                        <div role="group" aria-label={t('REPORT.CARD_REGION')} aria-busy={isFetching} className="grid grid-cols-1 gap-4 md:grid-cols-6">
                            {cards.map((card, index) => (
                                <ReportCard
                                    key={card.id}
                                    def={card}
                                    result={resultById.get(card.id)}
                                    catalogue={catalogue}
                                    loading={isFetching}
                                    first={index === 0}
                                    last={index === cards.length - 1}
                                    onChange={(next) => change(index, next)}
                                    onRemove={() => remove(index)}
                                    onMove={(delta) => move(index, delta)}
                                />
                            ))}
                        </div>
                    )}
                    {catalogue.fields.length === 0 && !empty && <p className="m-0 text-sm text-black-700">{t('REPORT.NOT_REPORTABLE_ANY')}</p>}
                    {hasTime && <p className="m-0 text-xs text-black-600">{t('REPORT.TZ_NOTE', { zone: tz })}</p>}

                    <div className="flex flex-wrap items-center gap-3">
                        {adding ? (
                            <div className="w-full">
                                <h3 className="m-0 mb-2 text-sm font-semibold text-black-900">{t('REPORT.ADD_CARD_TITLE')}</h3>
                                <ReportCardEditor
                                    initial={blankCard()}
                                    catalogue={catalogue}
                                    applyLabel={t('REPORT.ADD')}
                                    onCancel={() => {
                                        setAdding(false);
                                        addRef.current?.focus();
                                    }}
                                    onApply={(card) => {
                                        setAdding(false);
                                        setCards([...cards, card]);
                                    }}
                                />
                            </div>
                        ) : (
                            <Button ref={addRef} type="button" variant="v2Button" className="h-10 gap-2 px-4" icon={<Plus className="h-4 w-4" aria-hidden="true" />} disabled={cards.length >= catalogue.limits.maxCards} onClick={() => setAdding(true)}>
                                {t('REPORT.ADD_CARD')}
                            </Button>
                        )}
                        {!urlCards && questionCount > OVERVIEW_QUESTIONS && (
                            <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => write({ all: !all }, true)}>
                                {all ? t('REPORT.SHOW_FIRST', { count: OVERVIEW_QUESTIONS }) : t('REPORT.SHOW_ALL', { count: questionCount })}
                            </Button>
                        )}
                        {urlCards && (
                            <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => write({ cards: null }, true)}>
                                {t('REPORT.RESET')}
                            </Button>
                        )}
                    </div>
                </>
            ) : null}
        </div>
    );
}
