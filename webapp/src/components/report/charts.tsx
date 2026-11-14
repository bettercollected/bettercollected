'use client';

/**
 * The marks of a report, drawn as SVG by hand (no chart library): a number tile,
 * a bar chart, a donut, a line (or columns, for a few points) over time and the
 * table every card can be read as. Each takes the view model of
 * `utils/report-view.ts` and draws it, nothing else.
 *
 * Reading them without sight or colour: every mark has its value written next to
 * it (never only on hover); the slices of a donut differ by a pattern as well as by
 * colour, and its legend names each with its value; a chart is one image
 * (`role="img"`) described by a sentence, and the figures are in the table that
 * follows it. Marks are not tab stops; the table is the way in. A region that
 * scrolls sideways on a narrow screen becomes a tab stop only while it does.
 */
import React, { useEffect, useId, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { cn } from '@app/shadcn/util/lib';
import { CardView, ReportRow, valueWithShare } from '@app/utils/report-view';

/* ---------------------------------------------------------- helpers */

/** A sideways-scrolling box is reachable by keyboard only while its content overflows it. */
export function ScrollBox({ label, className, children, boxRef }: { label: string; className?: string; children: React.ReactNode; boxRef?: React.RefObject<HTMLDivElement | null> }) {
    const own = useRef<HTMLDivElement>(null);
    const ref = boxRef ?? own;
    const [scrolls, setScrolls] = useState(false);
    useEffect(() => {
        const element = ref.current;
        if (!element) return;
        const measure = () => setScrolls(element.scrollWidth > element.clientWidth + 1);
        measure();
        if (typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(measure);
        observer.observe(element);
        return () => observer.disconnect();
    }, [ref]);
    return (
        <div ref={ref} role={scrolls ? 'region' : undefined} aria-label={scrolls ? label : undefined} tabIndex={scrolls ? 0 : undefined} className={cn('overflow-x-auto rounded focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden', className)}>
            {children}
        </div>
    );
}

/** The width of a box, once it is laid out (0 before, and in a test). */
function useBoxWidth(ref: React.RefObject<HTMLElement | null>): number {
    const [width, setWidth] = useState(0);
    useEffect(() => {
        const element = ref.current;
        if (!element) return;
        const measure = () => setWidth(Math.floor(element.clientWidth));
        measure();
        if (typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(measure);
        observer.observe(element);
        return () => observer.disconnect();
    }, [ref]);
    return width;
}

/** A round axis maximum: 1, 2 or 5 times a power of ten. */
export function niceMax(value: number): number {
    if (!(value > 0)) return 1;
    const power = Math.pow(10, Math.floor(Math.log10(value)));
    const scaled = value / power;
    return (scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10) * power;
}

interface ChartProps {
    view: CardView;
    summaryId: string;
    label: string;
    locale: string;
}

const imgProps = (props: ChartProps) => ({ role: 'img' as const, 'aria-label': props.label, 'aria-describedby': props.summaryId });

/* -------------------------------------------------------------- tile */

export function TileChart({ view, summaryId, label }: ChartProps) {
    return (
        <div role="img" aria-label={label} aria-describedby={summaryId} className="flex flex-col gap-1">
            <p aria-hidden="true" className="m-0 text-4xl leading-tight font-semibold tracking-tight text-black-900 tabular-nums">
                {view.headline ?? '–'}
            </p>
        </div>
    );
}

/* --------------------------------------------------------------- bar */

export function BarChart(props: ChartProps) {
    const { view } = props;
    const max = Math.max(0, ...view.rows.map((row) => row.value ?? 0));
    return (
        <ul {...imgProps(props)} className="m-0 flex list-none flex-col gap-2.5 p-0">
            {view.rows.map((row) => {
                const width = row.value !== null && row.value > 0 && max > 0 ? Math.max(1, (row.value / max) * 100) : 0;
                return (
                    <li aria-hidden="true" key={row.key} className="flex flex-col gap-1 sm:grid sm:grid-cols-[minmax(5rem,11rem)_minmax(0,1fr)_minmax(4.5rem,auto)] sm:items-center sm:gap-x-3">
                        <span className="min-w-0 text-sm leading-snug text-black-800 [overflow-wrap:anywhere]">{row.label}</span>
                        <div className="flex items-center gap-3 sm:contents">
                            <svg viewBox="0 0 100 14" preserveAspectRatio="none" focusable="false" className="h-3.5 w-full min-w-0 flex-1 overflow-hidden rounded-sm">
                                <rect x="0" y="0" width="100" height="14" style={{ fill: 'var(--viz-track)' }} />
                                {width > 0 && <rect x="0" y="0" width={width} height="14" style={{ fill: 'var(--series-1)' }} />}
                            </svg>
                            <span className="shrink-0 text-right text-sm font-medium text-black-900 tabular-nums">{valueWithShare(row)}</span>
                        </div>
                    </li>
                );
            })}
        </ul>
    );
}

/* ------------------------------------------------------------- donut */

const SIZE = 160;
const CENTRE = SIZE / 2;
const OUTER = 74;
const INNER = 44;

function arc(from: number, to: number): string {
    // angles in turns, from twelve o'clock, clockwise
    const point = (turn: number, radius: number) => [CENTRE + radius * Math.sin(turn * 2 * Math.PI), CENTRE - radius * Math.cos(turn * 2 * Math.PI)];
    const [x1, y1] = point(from, OUTER);
    const [x2, y2] = point(to, OUTER);
    const [x3, y3] = point(to, INNER);
    const [x4, y4] = point(from, INNER);
    const large = to - from > 0.5 ? 1 : 0;
    return `M${x1},${y1} A${OUTER},${OUTER} 0 ${large} 1 ${x2},${y2} L${x3},${y3} A${INNER},${INNER} 0 ${large} 0 ${x4},${y4} Z`;
}

/** The fill of series `index`: its colour, and a pattern over it for every one after the first. */
function PatternDefs({ id, count }: { id: string; count: number }) {
    const base = (index: number) => ({ fill: `var(--series-${index + 1})` });
    const line = { stroke: 'var(--viz-surface)', strokeWidth: 2 } as const;
    return (
        <defs>
            {Array.from({ length: count }, (_, index) => (
                <pattern key={index} id={`${id}-${index}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform={index === 1 || index === 3 ? 'rotate(45)' : undefined}>
                    <rect width="6" height="6" style={base(index)} />
                    {(index === 1 || index === 4) && <line x1="0" y1="3" x2="6" y2="3" style={line} />}
                    {index === 2 && <circle cx="3" cy="3" r="1.4" style={{ fill: 'var(--viz-surface)' }} />}
                    {index === 3 && (
                        <>
                            <line x1="0" y1="3" x2="6" y2="3" style={line} />
                            <line x1="3" y1="0" x2="3" y2="6" style={line} />
                        </>
                    )}
                    {index === 5 && <line x1="3" y1="0" x2="3" y2="6" style={line} />}
                </pattern>
            ))}
        </defs>
    );
}

export function DonutChart(props: ChartProps) {
    const { view, locale } = props;
    const id = useId().replace(/:/g, '');
    const slices = view.rows.filter((row) => (row.value ?? 0) > 0);
    const total = slices.reduce((sum, row) => sum + (row.value ?? 0), 0);
    let start = 0;
    return (
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <svg {...imgProps(props)} viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-40 w-40 shrink-0">
                <PatternDefs id={id} count={view.rows.length} />
                {slices.length === 1 ? (
                    <path d={`${arc(0, 0.5)} ${arc(0.5, 1)}`} style={{ fill: `url(#${id}-${view.rows.indexOf(slices[0])})` }} />
                ) : (
                    slices.map((row) => {
                        const share = (row.value ?? 0) / total;
                        const piece = arc(start, start + share);
                        start += share;
                        return <path key={row.key} d={piece} style={{ fill: `url(#${id}-${view.rows.indexOf(row)})`, stroke: 'var(--viz-surface)', strokeWidth: 2 }} />;
                    })
                )}
                <text x={CENTRE} y={CENTRE + 6} textAnchor="middle" className="fill-black-900 text-[20px] font-semibold">
                    {slices.length ? new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(view.rows.reduce((sum, row) => sum + (row.value ?? 0), 0)) : '–'}
                </text>
            </svg>
            <ul aria-hidden="true" className="m-0 flex min-w-0 flex-1 list-none flex-col gap-2 p-0">
                {view.rows.map((row, index) => (
                    <li key={row.key} className="flex items-center gap-2.5 text-sm">
                        <svg viewBox="0 0 14 14" className="h-3.5 w-3.5 shrink-0" focusable="false">
                            <rect width="14" height="14" rx="2" style={{ fill: `url(#${id}-${index})` }} />
                        </svg>
                        <span className="min-w-0 flex-1 text-black-800 [overflow-wrap:anywhere]">{row.label}</span>
                        <span className="shrink-0 font-medium text-black-900 tabular-nums">{valueWithShare(row)}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

/* -------------------------------------------------------------- line */

const HEIGHT = 224;
const MARGIN = { top: 22, right: 14, bottom: 36, left: 44 };
/** Up to this many points are drawn as columns; more as a line. */
export const COLUMNS_MAX = 14;

export function LineChart(props: ChartProps) {
    const { view, label, locale } = props;
    const points = view.rows;
    const n = points.length;
    const columns = n <= COLUMNS_MAX;
    // at least the room the points need (the box then scrolls on a narrow screen), else the box's own width
    const boxRef = useRef<HTMLDivElement>(null);
    const room = useBoxWidth(boxRef);
    const needed = Math.max(320, columns ? n * 48 + MARGIN.left + MARGIN.right : n * 16 + MARGIN.left + MARGIN.right);
    const width = Math.min(1600, Math.max(needed, room));
    const plotWidth = width - MARGIN.left - MARGIN.right;
    const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
    const top = niceMax(Math.max(0, ...points.map((row) => row.value ?? 0)));
    // below zero too: the axis then runs from a round minimum to the round maximum, with the zero line between
    const lowest = Math.min(0, ...points.map((row) => row.value ?? 0));
    const bottom = lowest < 0 ? -niceMax(-lowest) : 0;
    const x = (index: number) => MARGIN.left + (columns ? (plotWidth / n) * (index + 0.5) : n === 1 ? plotWidth / 2 : (plotWidth / (n - 1)) * index);
    const y = (value: number) => MARGIN.top + plotHeight - ((value - bottom) / (top - bottom)) * plotHeight;
    const step = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(plotWidth / 72))));
    const numbers = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
    // a line labels its first, last and highest points; columns label each
    const highest = points.reduce((best, row, index) => ((row.value ?? -1) > (points[best].value ?? -1) ? index : best), 0);
    const labelled = new Set(columns ? points.map((_, index) => index) : [0, n - 1, highest]);
    const path = points.map((row, index) => (row.value === null ? null : `${x(index)},${y(row.value)}`));
    const segments: string[] = [];
    let run: string[] = [];
    for (const piece of path) {
        if (piece === null) {
            if (run.length) segments.push(run.join(' '));
            run = [];
        } else run.push(piece);
    }
    if (run.length) segments.push(run.join(' '));
    return (
        <ScrollBox label={label} boxRef={boxRef}>
            <svg {...imgProps(props)} viewBox={`0 0 ${width} ${HEIGHT}`} width={width} height={HEIGHT} className="block max-w-none">
                {[...new Set([bottom, 0, top])].map((tick) => (
                    <g key={tick}>
                        <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} style={{ stroke: tick === 0 ? 'var(--viz-grid)' : 'var(--viz-track)' }} strokeWidth="1" />
                        <text x={MARGIN.left - 8} y={y(tick) + 4} textAnchor="end" className="fill-black-700 text-[11px] tabular-nums">
                            {numbers.format(tick)}
                        </text>
                    </g>
                ))}
                {columns
                    ? points.map((row, index) => {
                          if (row.value === null) return null;
                          const barWidth = Math.min(28, (plotWidth / n) * 0.62);
                          // from the zero line up, or down for a negative value
                          const zero = y(0);
                          const end = y(row.value);
                          const height = Math.max(row.value !== 0 ? 1.5 : 0, Math.abs(zero - end));
                          return <rect key={row.key} x={x(index) - barWidth / 2} y={row.value < 0 ? zero : zero - height} width={barWidth} height={height} rx="2" style={{ fill: 'var(--series-1)' }} />;
                      })
                    : segments.map((segment) => <polyline key={segment} points={segment} fill="none" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" style={{ stroke: 'var(--series-1)' }} />)}
                {!columns &&
                    points.map((row, index) =>
                        row.value !== null && labelled.has(index) ? <circle key={row.key} cx={x(index)} cy={y(row.value)} r="4" strokeWidth="2" style={{ fill: 'var(--series-1)', stroke: 'var(--viz-surface)' }} /> : null
                    )}
                {points.map((row, index) =>
                    row.value !== null && labelled.has(index) ? (
                        <text key={`v${row.key}`} x={Math.min(width - 16, Math.max(MARGIN.left + 8, x(index)))} y={row.value < 0 && columns ? y(row.value) + 16 : y(row.value) - 8} textAnchor="middle" className="fill-black-900 text-[11px] font-medium tabular-nums">
                            {row.valueText}
                        </text>
                    ) : null
                )}
                {points.map((row, index) =>
                    index % step === 0 || (index === n - 1 && n - 1 - Math.floor((n - 1) / step) * step >= step * 0.75) ? (
                        <text key={`x${row.key}`} x={Math.min(width - MARGIN.right - 12, Math.max(MARGIN.left + 12, x(index)))} y={HEIGHT - 12} textAnchor="middle" className="fill-black-700 text-[11px]">
                            {row.axisLabel ?? row.label}
                        </text>
                    ) : null
                )}
            </svg>
        </ScrollBox>
    );
}

/* ------------------------------------------------------------- table */

export function DataTable({ view, caption, srOnly = false, onOpen }: { view: CardView; caption: string; srOnly?: boolean; onOpen?: (row: ReportRow) => void }) {
    const { t } = useTranslation();
    const hasShare = view.rows.some((row) => row.shareText);
    const showN = view.columns.length > 0 && view.columns[0].label !== t('REPORT.COL_N');
    const body = (
        <table className="w-full border-collapse text-left text-sm">
            <caption className="sr-only">{caption}</caption>
            <thead>
                <tr className="border-b border-black-300">
                    <th scope="col" className="min-w-24 py-2 pr-4 font-semibold text-black-800">
                        {view.groupHeader}
                    </th>
                    {view.columns.map((column) => (
                        <th key={column.key} scope="col" className="px-2 py-2 text-right font-semibold text-black-800">
                            {column.label}
                        </th>
                    ))}
                    {showN && (
                        <th scope="col" className="px-2 py-2 text-right font-semibold text-black-800">
                            {t('REPORT.COL_N')}
                        </th>
                    )}
                    {hasShare && (
                        <th scope="col" className="py-2 pl-2 text-right font-semibold text-black-800">
                            {t('REPORT.COL_SHARE')}
                        </th>
                    )}
                    {onOpen && (
                        <th scope="col" className="py-2 pl-3 text-right">
                            <span className="sr-only">{t('REPORT.COL_OPEN')}</span>
                        </th>
                    )}
                </tr>
            </thead>
            <tbody>
                {view.rows.map((row: ReportRow) => (
                    <tr key={row.key} className="border-b border-black-200 last:border-0">
                        <th scope="row" className="min-w-24 py-2 pr-4 font-normal text-black-900 [overflow-wrap:anywhere]">
                            {row.label}
                        </th>
                        {row.valuesText.map((text, index) => (
                            <td key={index} className="px-2 py-2 text-right text-black-900 tabular-nums">
                                {text}
                            </td>
                        ))}
                        {showN && <td className="px-2 py-2 text-right text-black-900 tabular-nums">{row.n}</td>}
                        {hasShare && <td className="py-2 pl-2 text-right text-black-900 tabular-nums">{row.shareText ?? ''}</td>}
                        {onOpen && (
                            <td className="py-1 pl-3 text-right">
                                {row.n > 0 && (
                                    <button
                                        type="button"
                                        onClick={() => onOpen(row)}
                                        aria-label={t('REPORT.OPEN_RESPONSES_OF', { group: row.label })}
                                        className="min-h-9 rounded px-1 text-right text-sm font-medium text-brand-600 underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                                    >
                                        {t('REPORT.OPEN_RESPONSES')}
                                    </button>
                                )}
                            </td>
                        )}
                    </tr>
                ))}
                {view.otherGroups && (
                    <tr className="border-b border-black-200 last:border-0">
                        <th scope="row" className="py-2 pr-4 font-normal text-black-900">
                            {view.otherGroups.label}
                        </th>
                        {view.columns.map((column, index) => (
                            <td key={column.key} className="px-2 py-2 text-right text-black-900 tabular-nums">
                                {index === 0 && !showN ? view.otherGroups?.n : ''}
                            </td>
                        ))}
                        {showN && <td className="px-2 py-2 text-right text-black-900 tabular-nums">{view.otherGroups.n}</td>}
                        {hasShare && <td />}
                        {onOpen && <td />}
                    </tr>
                )}
            </tbody>
        </table>
    );
    return srOnly ? <div className="sr-only">{body}</div> : <ScrollBox label={caption}>{body}</ScrollBox>;
}
