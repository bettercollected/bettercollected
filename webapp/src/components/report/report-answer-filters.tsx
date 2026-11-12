'use client';

/**
 * Answer filters of the Report page: which responses the report is about, by what they answered.
 * A condition is a question, an operator the question's kind takes and a value that is one of its
 * options, a number, a yes/no or a date (never text). The ones in force show as removable chips;
 * a plain form adds one. They live in the address (`report-page.tsx`) and are checked by the
 * server like the rest of the definition.
 */
import React, { useEffect, useId, useRef, useState } from 'react';

import { Plus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import { Button } from '@app/shadcn/components/ui/button';
import { CLAUSES_MAX, ReportCatalogue, ReportClause, ReportField, fieldOf } from '@app/utils/report';
import { LIST_OPS, NO_VALUE_OPS, PAIR_OPS, clauseProblem, describeClause, filterableFields } from '@app/utils/report-where';

const control = 'border-black-300 text-black-900 focus-visible:ring-brand-500 h-10 w-full rounded border bg-white py-0 pr-9 pl-3 text-sm text-ellipsis focus:outline-hidden focus-visible:ring-2';
const input = 'border-black-300 text-black-900 focus-visible:ring-brand-500 h-10 w-full rounded border bg-white px-3 py-0 text-sm focus:outline-hidden focus-visible:ring-2';

interface Draft {
    field: string;
    op: string;
    single: string;
    pair: [string, string];
    picks: string[];
}

/** What a draft says for `field`: the options, or true, or nothing, to start from. */
function draftFor(field: ReportField, op: string = (field.filterOps ?? [])[0] ?? 'is'): Draft {
    const first = field.options?.[0]?.id;
    return { field: field.key, op, single: field.kind === 'choice' || field.kind === 'choices' ? (first ?? '') : op === 'is' ? 'true' : '', pair: ['', ''], picks: first ? [first] : [] };
}

/** The condition a draft stands for (a number the person has not typed is NaN, which no check accepts). */
export function clauseOf(draft: Draft, field: ReportField): ReportClause {
    const { op } = draft;
    if (NO_VALUE_OPS.includes(op)) return { field: draft.field, op };
    if (field.kind === 'choice' || field.kind === 'choices') return { field: draft.field, op, value: LIST_OPS.includes(op) ? draft.picks : draft.single };
    if (op === 'is') return { field: draft.field, op, value: draft.single === 'true' };
    const parse = (value: string) => (field.kind === 'date' ? value : value.trim() === '' ? Number.NaN : Number(value));
    return { field: draft.field, op, value: PAIR_OPS.includes(op) ? [parse(draft.pair[0]), parse(draft.pair[1])] as Array<number | string> : parse(draft.single) };
}

interface Props {
    catalogue: ReportCatalogue;
    clauses: ReportClause[];
    onChange: (next: ReportClause[]) => void;
}

export default function ReportAnswerFilters({ catalogue, clauses, onChange }: Props) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const id = useId();
    const fields = filterableFields(catalogue);
    const [open, setOpen] = useState(false);
    const [draft, setDraft] = useState<Draft | undefined>();
    const addRef = useRef<HTMLButtonElement>(null);
    const fieldRef = useRef<HTMLSelectElement>(null);
    const full = clauses.length >= CLAUSES_MAX;
    useEffect(() => {
        if (open) fieldRef.current?.focus();
    }, [open]);
    if (fields.length === 0 && clauses.length === 0) return null;

    const field = draft ? fieldOf(catalogue, draft.field) : undefined;
    const clause = draft && field ? clauseOf(draft, field) : undefined;
    const problem = clause ? clauseProblem(clause, catalogue) : 'invalid';
    const start = () => {
        setDraft(draftFor(fields[0]));
        setOpen(true);
    };
    const close = () => {
        setOpen(false);
        addRef.current?.focus();
    };
    const chips = clauses.map((item) => ({ item, text: describeClause(item, catalogue, t, locale), gone: !fieldOf(catalogue, item.field) }));
    const update = (changes: Partial<Draft>) => setDraft((current) => (current ? { ...current, ...changes } : current));
    const ops = field?.filterOps ?? [];

    return (
        <section aria-label={t('REPORT.ANSWER_FILTERS')} className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
                <Button ref={addRef} type="button" variant="v2Button" className="h-10 gap-2 px-4" icon={<Plus className="h-4 w-4" aria-hidden="true" />} aria-expanded={open} disabled={full || fields.length === 0} onClick={() => (open ? close() : start())}>
                    {t('REPORT.ADD_ANSWER_FILTER')}
                </Button>
                {full && <span className="text-xs text-black-600">{t('REPORT.ANSWER_FILTERS_FULL', { count: CLAUSES_MAX })}</span>}
            </div>

            {chips.length > 0 && (
                <ul aria-label={t('REPORT.ACTIVE_ANSWER_FILTERS')} className="m-0 flex list-none flex-wrap items-center gap-2 p-0">
                    {chips.map(({ item, text, gone }, index) => (
                        <li key={`${item.field}-${index}`} className="flex items-center gap-1 rounded-full bg-brand-100 py-0.5 pr-1 pl-3 text-sm text-black-900">
                            <span>{gone ? `${text} (${t('REPORT.UNAVAILABLE_FIELD')})` : text}</span>
                            <button
                                type="button"
                                aria-label={t('REPORT.REMOVE_ANSWER_FILTER', { filter: text })}
                                className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-brand-200 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500"
                                onClick={() => onChange(clauses.filter((_, at) => at !== index))}
                            >
                                <X className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                    <li>
                        <button type="button" onClick={() => onChange([])} className="rounded text-sm font-medium text-brand-500 underline-offset-2 hover:underline focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500">
                            {t('REPORT.CLEAR_ANSWER_FILTERS')}
                        </button>
                    </li>
                </ul>
            )}

            {open && draft && field && (
                <form
                    aria-label={t('REPORT.ADD_ANSWER_FILTER')}
                    className="grid grid-cols-1 gap-3 rounded border border-black-300 bg-white p-4 min-[560px]:grid-cols-2 lg:grid-cols-3"
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (clause && !problem) {
                            onChange([...clauses, clause]);
                            close();
                        }
                    }}
                    onKeyDown={(event) => {
                        if (event.key === 'Escape') close();
                    }}
                >
                    <div className="flex min-w-0 flex-col gap-1">
                        <label htmlFor={`${id}-q`} className="p4-new text-black-700">
                            {t('REPORT.ANSWER_QUESTION')}
                        </label>
                        <select ref={fieldRef} id={`${id}-q`} className={control} value={draft.field} onChange={(event) => setDraft(draftFor(fieldOf(catalogue, event.target.value) as ReportField))}>
                            {fields.map((item) => (
                                <option key={item.key} value={item.key}>
                                    {item.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="flex min-w-0 flex-col gap-1">
                        <label htmlFor={`${id}-op`} className="p4-new text-black-700">
                            {t('REPORT.ANSWER_CONDITION')}
                        </label>
                        <select id={`${id}-op`} className={control} value={draft.op} onChange={(event) => setDraft(draftFor(field, event.target.value))}>
                            {ops.map((op) => (
                                <option key={op} value={op}>
                                    {t(`REPORT.OP.${op}`)}
                                </option>
                            ))}
                        </select>
                    </div>
                    {!NO_VALUE_OPS.includes(draft.op) && (
                        <div className="flex min-w-0 flex-col gap-1 min-[560px]:col-span-2 lg:col-span-1">
                            {(field.kind === 'choice' || field.kind === 'choices') && LIST_OPS.includes(draft.op) ? (
                                <fieldset className="m-0 flex min-w-0 flex-col gap-1 border-0 p-0">
                                    <legend className="p4-new mb-1 text-black-700">{t('REPORT.ANSWER_VALUE')}</legend>
                                    {(field.options ?? []).map((option) => (
                                        <label key={option.id} className="flex items-center gap-2 text-sm text-black-900">
                                            <input
                                                type="checkbox"
                                                checked={draft.picks.includes(option.id)}
                                                onChange={(event) => update({ picks: event.target.checked ? [...draft.picks, option.id] : draft.picks.filter((pick) => pick !== option.id) })}
                                            />
                                            {option.label}
                                        </label>
                                    ))}
                                </fieldset>
                            ) : (field.kind === 'choice' || field.kind === 'choices') ? (
                                <>
                                    <label htmlFor={`${id}-v`} className="p4-new text-black-700">
                                        {t('REPORT.ANSWER_VALUE')}
                                    </label>
                                    <select id={`${id}-v`} className={control} value={draft.single} onChange={(event) => update({ single: event.target.value })}>
                                        {(field.options ?? []).map((option) => (
                                            <option key={option.id} value={option.id}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </>
                            ) : draft.op === 'is' ? (
                                <>
                                    <label htmlFor={`${id}-v`} className="p4-new text-black-700">
                                        {t('REPORT.ANSWER_VALUE')}
                                    </label>
                                    <select id={`${id}-v`} className={control} value={draft.single} onChange={(event) => update({ single: event.target.value })}>
                                        <option value="true">{t('REPORT.GROUP.yes')}</option>
                                        <option value="false">{t('REPORT.GROUP.no')}</option>
                                    </select>
                                </>
                            ) : PAIR_OPS.includes(draft.op) ? (
                                <div className="grid grid-cols-2 gap-2">
                                    {[0, 1].map((at) => (
                                        <div key={at} className="flex min-w-0 flex-col gap-1">
                                            <label htmlFor={`${id}-v${at}`} className="p4-new text-black-700">
                                                {at === 0 ? t('REPORT.VALUE_FROM') : t('REPORT.VALUE_TO')}
                                            </label>
                                            <input
                                                id={`${id}-v${at}`}
                                                className={input}
                                                type={field.kind === 'date' ? 'date' : 'number'}
                                                step={field.kind === 'date' ? undefined : 'any'}
                                                value={draft.pair[at]}
                                                onChange={(event) => update({ pair: (at === 0 ? [event.target.value, draft.pair[1]] : [draft.pair[0], event.target.value]) as [string, string] })}
                                            />
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <>
                                    <label htmlFor={`${id}-v`} className="p4-new text-black-700">
                                        {t('REPORT.ANSWER_VALUE')}
                                    </label>
                                    <input id={`${id}-v`} className={input} type={field.kind === 'date' ? 'date' : 'number'} step={field.kind === 'date' ? undefined : 'any'} value={draft.single} onChange={(event) => update({ single: event.target.value })} />
                                </>
                            )}
                        </div>
                    )}
                    <div className="flex items-end gap-2 min-[560px]:col-span-2 lg:col-span-3">
                        <Button type="submit" variant="primary" className="h-10 px-4" disabled={!!problem}>
                            {t('REPORT.ADD')}
                        </Button>
                        <Button type="button" variant="v2Button" className="h-10 px-4" onClick={close}>
                            {t('REPORT.CANCEL')}
                        </Button>
                    </div>
                </form>
            )}
        </section>
    );
}
