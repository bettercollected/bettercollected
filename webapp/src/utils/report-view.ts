/**
 * What a report card shows, worked out from its definition, the server's figures
 * and the form's catalogue: the title, the rows (a label, a value and a share,
 * all as text in the viewer's language and locale), the headline of a number tile
 * and the sentences a screen reader gets. The chart components only draw this.
 */
import {
    DONUT_MAX,
    ReportAgg,
    ReportBucket,
    ReportCardDef,
    ReportCardKind,
    ReportCardResult,
    ReportCatalogue,
    ReportField,
    ReportGroup,
    bucketLabel,
    builtinOf,
    fieldOf,
    isTimeDimension
} from '@app/utils/report';

export type Translate = (key: string, options?: Record<string, unknown>) => string;

export interface ReportRow {
    key: string;
    label: string;
    /** A shorter label for a chart's axis (a day without its year). */
    axisLabel?: string;
    /** Responses in the group. */
    n: number;
    /** The first measure's figure; null when nobody answered (an average over no answers). */
    value: number | null;
    valueText: string;
    /** The figure of every measure, as text. */
    valuesText: string[];
    /** Share of the answered responses, 0 to 1, for a count. */
    share?: number;
    shareText?: string;
}

export interface ReportColumn {
    key: string;
    label: string;
}

export interface CardView {
    id: string;
    title: string;
    /** The kind drawn: a donut with too many slices (or not a count) is a bar. */
    kind: ReportCardKind;
    asked: ReportCardKind;
    rows: ReportRow[];
    columns: ReportColumn[];
    groupHeader: string;
    otherGroups?: { n: number; count: number; label: string };
    n: number;
    answered: number;
    skipped: number;
    multiple: boolean;
    truncated: boolean;
    empty: boolean;
    time: boolean;
    bucket?: ReportBucket;
    /** A number tile's figure. */
    headline?: string;
    /** `n = 130` (or, with a dimension, "130 of 212 answered"). */
    basis: string;
}

const AGG_KEY: Record<ReportAgg, string> = { count: 'REPORT.COUNT', avg: 'REPORT.AVERAGE', sum: 'REPORT.SUM', min: 'REPORT.MIN', max: 'REPORT.MAX' };

export function numberFormat(locale: string, options?: Intl.NumberFormatOptions) {
    try {
        return new Intl.NumberFormat(locale, { maximumFractionDigits: 2, ...options });
    } catch {
        return new Intl.NumberFormat('en', { maximumFractionDigits: 2, ...options });
    }
}

export function dimensionLabel(catalogue: ReportCatalogue, key: string, t: Translate): string {
    const field = fieldOf(catalogue, key);
    if (field) return field.label;
    return builtinOf(catalogue, key) ? t(`REPORT.BUILTIN.${key}`) : key;
}

export function aggLabel(agg: ReportAgg, t: Translate): string {
    return t(AGG_KEY[agg]);
}

/** A group's label in the viewer's language: the server names the fixed groups in English. */
export function groupLabel(group: ReportGroup, dimensionKey: string | undefined, catalogue: ReportCatalogue, t: Translate, locale: string, bucket?: ReportBucket): string {
    const key = group.key;
    const field = fieldOf(catalogue, dimensionKey);
    if (dimensionKey && isTimeDimension(catalogue, dimensionKey)) return bucketLabel(key, bucket, locale);
    if (field && (field.kind === 'choice' || field.kind === 'choices')) {
        if (key === 'other') return t('REPORT.OTHER');
        if (key === 'removed') return t('REPORT.REMOVED_OPTION');
        return group.label || key;
    }
    if (field && (field.kind === 'yes_no' || field.kind === 'calculated')) return key === 'yes' || key === 'no' ? t(`REPORT.GROUP.${key}`) : group.label || key;
    if (dimensionKey === 'form_version') return t('REPORT.VERSION_N', { n: key });
    if (dimensionKey === 'ending') return key === 'none' ? t('REPORT.GROUP.none_ending') : key === 'removed' ? t('REPORT.REMOVED_OPTION') : group.label || key;
    if (dimensionKey === 'status') return ['none', 'pending', 'declined', 'success'].includes(key) ? t(key === 'none' ? 'REPORT.GROUP.none_status' : `REPORT.GROUP.${key}`) : group.label || key;
    if (dimensionKey === 'feedback_status') return key === 'none' ? t('REPORT.GROUP.none_feedback') : group.label || key;
    if (dimensionKey === 'respondent' || dimensionKey === 'source') return ['anonymous', 'known', 'form', 'api', 'csv'].includes(key) ? t(`REPORT.GROUP.${key}`) : group.label || key;
    return group.label || key;
}

export function cardTitle(def: ReportCardDef, catalogue: ReportCatalogue, t: Translate): string {
    if (def.title) return def.title;
    const measure = def.measures[0];
    const dimension = def.dimension?.field;
    const valueField = fieldOf(catalogue, measure?.field);
    const value = measure && measure.agg !== 'count' ? `${aggLabel(measure.agg, t)} · ${valueField?.label ?? measure.field ?? ''}` : undefined;
    if (!dimension) return value ?? t('REPORT.RESPONSES_TOTAL');
    const by = dimensionLabel(catalogue, dimension, t);
    if (!value) return dimension === 'submitted_at' ? t('REPORT.OVER_TIME') : by;
    return `${value} (${t('REPORT.GROUP_BY').toLowerCase()} ${by})`;
}

function formatValue(value: number | null | undefined, agg: ReportAgg, field: ReportField | undefined, locale: string): string {
    if (value === null || value === undefined) return '–';
    if (agg !== 'count' && field?.kind === 'currency') {
        try {
            return numberFormat(locale, { style: 'currency', currency: field.currency || 'EUR' }).format(value);
        } catch {
            /* an unknown code: a plain number */
        }
    }
    return numberFormat(locale).format(value);
}

/** The view of one card. `result` may be missing while figures load or when the card was not asked for. */
export function buildCardView(def: ReportCardDef, result: ReportCardResult | undefined, catalogue: ReportCatalogue, t: Translate, locale: string): CardView {
    const dimensionKey = def.dimension?.field;
    const bucket = def.dimension?.bucket ?? (dimensionKey && isTimeDimension(catalogue, dimensionKey) ? 'day' : undefined);
    const percent = numberFormat(locale, { style: 'percent', maximumFractionDigits: 0 });
    const first = def.measures[0] ?? { agg: 'count' as ReportAgg };
    const firstField = fieldOf(catalogue, first.field);
    const answered = result?.answered ?? 0;
    const total = result?.n ?? 0;
    const groups = result?.groups ?? [];
    // the options nobody chose and the "Other" and "Removed option" groups nobody is in are not listed
    const shown = groups.filter((group) => !((group.key === 'other' || group.key === 'removed') && group.n === 0 && fieldOf(catalogue, dimensionKey)?.kind !== undefined && ['choice', 'choices'].includes(fieldOf(catalogue, dimensionKey)?.kind ?? '')));
    const rows: ReportRow[] = shown.map((group) => {
        const values = def.measures.map((measure, index) => formatValue(group.values[index], measure.agg, fieldOf(catalogue, measure.field), locale));
        const row: ReportRow = {
            axisLabel: dimensionKey && isTimeDimension(catalogue, dimensionKey) ? bucketLabel(group.key, bucket, locale, true) : undefined,
            key: group.key,
            label: dimensionKey ? groupLabel(group, dimensionKey, catalogue, t, locale, bucket) : t('REPORT.RESPONSES_TOTAL'),
            n: group.n,
            value: group.values[0] ?? null,
            valueText: values[0] ?? '–',
            valuesText: values
        };
        if (dimensionKey && first.agg === 'count' && answered > 0) {
            row.share = group.n / answered;
            row.shareText = percent.format(row.share);
        }
        return row;
    });
    // a donut is parts of a whole: a count with few groups, all of them positive; otherwise a bar
    let kind = def.kind;
    if (kind === 'donut' && (first.agg !== 'count' || rows.length > DONUT_MAX || rows.length < 1 || rows.some((row) => (row.value ?? 0) < 0))) kind = 'bar';
    const columns: ReportColumn[] = def.measures.map((measure, index) => ({
        key: `m${index}`,
        label: measure.agg === 'count' ? t('REPORT.COL_N') : `${aggLabel(measure.agg, t)} · ${fieldOf(catalogue, measure.field)?.label ?? measure.field ?? ''}`
    }));
    const other = result?.otherGroups;
    return {
        id: def.id,
        title: cardTitle(def, catalogue, t),
        kind,
        asked: def.kind,
        rows,
        columns,
        groupHeader: dimensionKey ? dimensionLabel(catalogue, dimensionKey, t) : t('REPORT.COL_GROUP'),
        otherGroups: other && other.count > 0 ? { n: other.n, count: other.count, label: t('REPORT.OTHER_GROUPS', { count: other.count }) } : undefined,
        n: total,
        answered,
        skipped: result?.skipped ?? 0,
        multiple: !!result?.multiple,
        truncated: !!result?.truncated,
        empty: !!result && answered === 0,
        time: !!dimensionKey && isTimeDimension(catalogue, dimensionKey),
        bucket,
        headline: !dimensionKey ? (rows[0]?.valueText ?? '–') : undefined,
        basis: dimensionKey || first.agg !== 'count' ? t('REPORT.ANSWERED_OF', { answered: numberFormat(locale).format(answered), total: numberFormat(locale).format(total) }) : t('REPORT.N', { count: total })
    };
}

/** The sentence a screen reader gets for a chart (the table that follows has every figure). */
export function chartSummary(view: CardView, t: Translate): string {
    const kind = t(`REPORT.KIND.${view.kind}`);
    if (view.kind === 'tile') return t('REPORT.A11Y_TILE', { title: view.title, value: view.headline ?? '–' });
    const ranked = view.rows.filter((row) => row.value !== null);
    if (ranked.length === 0) return t('REPORT.A11Y_CHART', { title: view.title });
    const largest = ranked.reduce((best, row) => ((row.value ?? 0) > (best.value ?? 0) ? row : best), ranked[0]);
    const value = view.rows.length && largest.shareText ? `${largest.valueText} (${largest.shareText})` : largest.valueText;
    if (view.kind === 'line' || view.time) return t('REPORT.A11Y_LINE_SUMMARY', { kind, count: view.rows.length, first: view.rows[0].label, last: view.rows[view.rows.length - 1].label, label: largest.label, value });
    return t('REPORT.A11Y_SUMMARY', { kind, count: view.rows.length, label: largest.label, value });
}

/** `74 (37%)` for a count with a share, else the figure. */
export function valueWithShare(row: ReportRow): string {
    return row.shareText ? `${row.valueText} (${row.shareText})` : row.valueText;
}
