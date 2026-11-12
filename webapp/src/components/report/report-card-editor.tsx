'use client';

/**
 * The form that adds a card or changes one: what to group by, what to show
 * (a count, or an average, sum, lowest or highest of a question), per what time
 * for a date, and as which chart. Plain labelled selects. Changes are held here
 * and applied together (Apply / Add), so one edit asks the server once.
 */
import React, { useId, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { REPORT_AGGS, ReportAgg, ReportBucket, ReportCardDef, ReportCardKind, ReportCatalogue, bucketsOf, cardProblem, dimensionKeys, isTimeDimension, kindsFor, newCardId, numericFields } from '@app/utils/report';
import { aggLabel, dimensionLabel } from '@app/utils/report-view';

const control = 'border-black-300 text-black-900 focus-visible:ring-brand-500 h-10 w-full rounded border bg-white px-3 py-0 text-sm focus:outline-hidden focus-visible:ring-2';

/** The draft a new card starts from. */
export function blankCard(): ReportCardDef {
    return { id: newCardId(), kind: 'tile', measures: [{ agg: 'count' }] };
}

/** `draft` made consistent after a change: a kind, aggregate and question that suit what it is grouped by. */
export function settle(draft: ReportCardDef, catalogue: ReportCatalogue): ReportCardDef {
    const next: ReportCardDef = { ...draft, measures: draft.measures.map((measure) => ({ ...measure })) };
    const dimension = next.dimension?.field;
    const measure = next.measures[0] ?? { agg: 'count' as ReportAgg };
    // the status groups can only be counted
    const countOnly = dimension === 'status' || dimension === 'feedback_status';
    if (countOnly || measure.agg === 'count') next.measures = [{ agg: 'count' }];
    else if (!numericFields(catalogue, measure.agg).some((field) => field.key === measure.field)) {
        const first = numericFields(catalogue, measure.agg)[0];
        next.measures = [first ? { agg: measure.agg, field: first.key } : { agg: 'count' }];
    }
    if (dimension && isTimeDimension(catalogue, dimension)) next.dimension = { field: dimension, bucket: next.dimension?.bucket ?? (dimension === 'submitted_at' ? 'day' : 'month') };
    else if (dimension) next.dimension = { field: dimension };
    let kinds = kindsFor(catalogue, dimension);
    if (next.measures[0].agg !== 'count') kinds = kinds.filter((kind) => kind !== 'donut');
    if (!kinds.includes(next.kind)) next.kind = kinds[0];
    return next;
}

export default function ReportCardEditor({ initial, catalogue, applyLabel, onApply, onCancel }: { initial: ReportCardDef; catalogue: ReportCatalogue; applyLabel: string; onApply: (card: ReportCardDef) => void; onCancel: () => void }) {
    const { t } = useTranslation();
    const id = useId();
    const [draft, setDraft] = useState<ReportCardDef>(() => settle(initial, catalogue));
    const update = (changes: Partial<ReportCardDef>) => setDraft((current) => settle({ ...current, ...changes }, catalogue));
    const dimension = draft.dimension?.field;
    const measure = draft.measures[0] ?? { agg: 'count' as ReportAgg };
    const countOnly = dimension === 'status' || dimension === 'feedback_status';
    const aggs = REPORT_AGGS.filter((agg) => agg === 'count' || (!countOnly && numericFields(catalogue, agg).length > 0));
    const valueFields = measure.agg === 'count' ? [] : numericFields(catalogue, measure.agg);
    const kinds = kindsFor(catalogue, dimension).filter((kind) => measure.agg === 'count' || kind !== 'donut');
    const buckets = bucketsOf(catalogue, dimension);
    const problem = cardProblem(draft, catalogue);
    const dimensions = dimensionKeys(catalogue);

    return (
        <form
            aria-label={t('REPORT.ADD_CARD_TITLE')}
            className="grid grid-cols-1 gap-3 rounded border border-black-300 bg-white p-4 min-[560px]:grid-cols-2 lg:grid-cols-3"
            onSubmit={(event) => {
                event.preventDefault();
                if (!problem) onApply(draft);
            }}
            onKeyDown={(event) => {
                if (event.key === 'Escape') onCancel();
            }}
        >
            <div className="flex min-w-0 flex-col gap-1">
                <label htmlFor={`${id}-by`} className="p4-new text-black-700">
                    {t('REPORT.GROUP_BY')}
                </label>
                <select id={`${id}-by`} className={control} value={dimension ?? ''} onChange={(event) => update({ dimension: event.target.value ? { field: event.target.value } : undefined })}>
                    <option value="">{t('REPORT.NO_GROUP')}</option>
                    {dimensions.map((key) => (
                        <option key={key} value={key}>
                            {dimensionLabel(catalogue, key, t)}
                        </option>
                    ))}
                </select>
            </div>
            {buckets.length > 0 && (
                <div className="flex min-w-0 flex-col gap-1">
                    <label htmlFor={`${id}-bucket`} className="p4-new text-black-700">
                        {t('REPORT.BUCKET')}
                    </label>
                    <select id={`${id}-bucket`} className={control} value={draft.dimension?.bucket ?? 'day'} onChange={(event) => update({ dimension: { field: dimension as string, bucket: event.target.value as ReportBucket } })}>
                        {buckets.map((bucket) => (
                            <option key={bucket} value={bucket}>
                                {t(`REPORT.BUCKET_OPTION.${bucket}`)}
                            </option>
                        ))}
                    </select>
                </div>
            )}
            <div className="flex min-w-0 flex-col gap-1">
                <label htmlFor={`${id}-agg`} className="p4-new text-black-700">
                    {t('REPORT.MEASURE')}
                </label>
                <select id={`${id}-agg`} className={control} value={measure.agg} onChange={(event) => update({ measures: [{ agg: event.target.value as ReportAgg }] })}>
                    {aggs.map((agg) => (
                        <option key={agg} value={agg}>
                            {aggLabel(agg, t)}
                        </option>
                    ))}
                </select>
            </div>
            {valueFields.length > 0 && (
                <div className="flex min-w-0 flex-col gap-1">
                    <label htmlFor={`${id}-field`} className="p4-new text-black-700">
                        {t('REPORT.VALUE_OF')}
                    </label>
                    <select id={`${id}-field`} className={control} value={measure.field ?? ''} onChange={(event) => update({ measures: [{ agg: measure.agg, field: event.target.value }] })}>
                        {valueFields.map((field) => (
                            <option key={field.key} value={field.key}>
                                {field.label}
                            </option>
                        ))}
                    </select>
                </div>
            )}
            <div className="flex min-w-0 flex-col gap-1">
                <label htmlFor={`${id}-kind`} className="p4-new text-black-700">
                    {t('REPORT.SHOW_AS')}
                </label>
                <select id={`${id}-kind`} className={cn(control)} value={draft.kind} onChange={(event) => update({ kind: event.target.value as ReportCardKind })}>
                    {kinds.map((kind) => (
                        <option key={kind} value={kind}>
                            {t(`REPORT.KIND_OPTION.${kind}`)}
                        </option>
                    ))}
                </select>
            </div>
            <div className="flex items-end gap-2 min-[560px]:col-span-2 lg:col-span-3">
                <Button type="submit" variant="primary" className="h-10 px-4" disabled={!!problem}>
                    {applyLabel}
                </Button>
                <Button type="button" variant="v2Button" className="h-10 px-4" onClick={onCancel}>
                    {t('REPORT.CANCEL')}
                </Button>
            </div>
        </form>
    );
}
