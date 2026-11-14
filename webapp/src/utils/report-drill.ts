/**
 * Drill-down: from a group of a card to the responses behind it. A group the responses list can
 * filter on by itself (a form version, anonymous or identified, a day, week, month or year of
 * submission) also has an address in that list; a group made of answers has not (the list has
 * no filter on an answer), so its responses are listed on the report page itself.
 */
import { ReportDimension } from '@app/utils/report';
import { ResponseListState } from '@app/utils/response-list-state';

const two = (value: number) => String(value).padStart(2, '0');
const day = (date: Date) => `${date.getUTCFullYear()}-${two(date.getUTCMonth() + 1)}-${two(date.getUTCDate())}`;

/** The first and last calendar day a time group covers (its key is the bucket's first day, `YYYY-MM` or `YYYY`). */
export function bucketDays(key: string, bucket: string | undefined): { from: string; to: string } | undefined {
    const parts = key.split('-').map(Number);
    if (parts.some((part) => !Number.isInteger(part))) return undefined;
    const [year, month = 1, date = 1] = parts;
    if (bucket === 'year' || /^\d{4}$/.test(key)) return { from: `${String(year).padStart(4, '0')}-01-01`, to: `${String(year).padStart(4, '0')}-12-31` };
    if (month < 1 || month > 12) return undefined;
    if (bucket === 'month' || /^\d{4}-\d{2}$/.test(key)) return { from: `${String(year).padStart(4, '0')}-${two(month)}-01`, to: day(new Date(Date.UTC(year, month, 0))) };
    const first = new Date(Date.UTC(year, month - 1, date));
    // a day that exists (2026-99-99 would roll over into another one)
    if (first.getUTCFullYear() !== year || first.getUTCMonth() !== month - 1 || first.getUTCDate() !== date) return undefined;
    if (bucket === 'week') return { from: day(first), to: day(new Date(Date.UTC(year, month - 1, date + 6))) };
    return { from: day(first), to: day(first) };
}

/**
 * The list filters that select the same responses as a group, over what the report's own list filters
 * already narrow to; undefined when the list cannot say it (a group of answers, or a report with
 * conditions on answers).
 */
export function listFiltersFor(dimension: ReportDimension | undefined, key: string, current: Pick<ResponseListState, 'from' | 'to' | 'status' | 'who' | 'version'>, hasWhere: boolean): Pick<ResponseListState, 'from' | 'to' | 'status' | 'who' | 'version'> | undefined {
    if (!dimension || hasWhere) return undefined;
    if (dimension.field === 'form_version') {
        const version = Number(key);
        return Number.isInteger(version) && version > 0 ? { ...current, version } : undefined;
    }
    if (dimension.field === 'respondent') return key === 'anonymous' || key === 'known' ? { ...current, who: key } : undefined;
    if (dimension.field === 'submitted_at') {
        const days = bucketDays(key, dimension.bucket);
        return days ? { ...current, from: days.from, to: days.to } : undefined;
    }
    return undefined;
}
