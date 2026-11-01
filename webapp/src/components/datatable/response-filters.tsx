import { useId, useRef, useState } from 'react';

import { SlidersHorizontal, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { responsesListLocale as text } from '@app/constants/locales/responses-list';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { calendarDayIn } from '@app/utils/date-utils';
import { DELETION_STATUSES, RESPONDENTS, ResponseListState, ResponseSort, SORTS, activeFilterCount } from '@app/utils/response-list-state';

const control = 'border-black-300 text-black-900 focus-visible:ring-brand-500 h-10 w-full rounded border bg-white px-3 py-0 text-sm focus:outline-hidden focus-visible:ring-2';

const STATUS_LABEL = { none: text.statusNone, pending: text.statusPending, declined: text.statusDeclined } as const;
const WHO_LABEL = { anonymous: text.whoAnonymous, known: text.whoKnown } as const;
const SORT_LABEL: Record<ResponseSort, string> = { newest: text.sortNewest, oldest: text.sortOldest, 'version-high': text.sortVersionHigh, 'version-low': text.sortVersionLow };

interface Props {
    state: ResponseListState;
    /** The form's current version: the versions offered are 1..this. */
    currentVersion?: number;
    /** Any change starts again on the first page; the cursor never survives it. */
    onChange: (changes: Partial<ResponseListState>) => void;
    onClear: () => void;
    /** The responder search: first in the toolbar row, taking the room left over. */
    search?: React.ReactNode;
    /** The export control: last in the toolbar row. */
    trailing?: React.ReactNode;
}

function Field({ id, label, children, className }: { id: string; label: string; children: React.ReactNode; className?: string }) {
    return (
        <div className={cn('flex min-w-0 flex-col gap-1', className)}>
            <label htmlFor={id} className="p4-new text-black-700">
                {label}
            </label>
            {children}
        </div>
    );
}

/**
 * The head of the responses list in one row: the responder search, a Filters
 * button that opens the submitted date range, deletion-request state,
 * anonymous or identified and form version, the sort, and the export. What
 * narrows the list stays in view as a row of removable chips, so a closed panel
 * never hides why the list is short. Every control is a native, labelled
 * field (keyboard and screen reader ready); a change is applied at once and
 * lives in the URL (the parent writes it).
 */
export default function ResponseFilters({ state, currentVersion, onChange, onClear, search, trailing }: Props) {
    const { t, i18n } = useTranslation();
    const id = useId();
    const panelId = `${id}-panel`;
    const [open, setOpen] = useState(false);
    const toggleRef = useRef<HTMLButtonElement>(null);
    const active = activeFilterCount(state);
    const versions = Array.from({ length: Math.min(Math.max(currentVersion ?? 1, state.version ?? 1), 200) }, (_, index) => index + 1).reverse();
    const versionLabel = (version: number) => t(version === currentVersion ? text.versionCurrent : text.versionN, { n: version });

    // The chips of what is in force, each with the change that removes it.
    const chips: Array<{ key: string; label: string; remove: Partial<ResponseListState> }> = [];
    if (state.from) chips.push({ key: 'from', label: t('RESPONSES_STAFF.CHIP_FROM', { date: calendarDayIn(state.from, i18n.language) }), remove: { from: undefined } });
    if (state.to) chips.push({ key: 'to', label: t('RESPONSES_STAFF.CHIP_TO', { date: calendarDayIn(state.to, i18n.language) }), remove: { to: undefined } });
    if (state.who) chips.push({ key: 'who', label: t('RESPONSES_STAFF.CHIP_WHO', { value: t(WHO_LABEL[state.who]) }), remove: { who: undefined } });
    if (state.status) chips.push({ key: 'status', label: t('RESPONSES_STAFF.CHIP_STATUS', { value: t(STATUS_LABEL[state.status]) }), remove: { status: undefined } });
    if (state.version) chips.push({ key: 'version', label: versionLabel(state.version), remove: { version: undefined } });

    return (
        <div className="mb-4 flex flex-col gap-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <form role="search" aria-label={t(text.filters)} className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end" onSubmit={(event) => event.preventDefault()}>
                    {search}
                    <Button
                        ref={toggleRef}
                        type="button"
                        variant="v2Button"
                        aria-expanded={open}
                        aria-controls={panelId}
                        className="h-10 shrink-0 gap-2 px-4 text-sm font-medium"
                        icon={<SlidersHorizontal className="h-4 w-4" aria-hidden="true" />}
                        onClick={() => setOpen((value) => !value)}
                    >
                        {t('RESPONSES_STAFF.FILTERS_BUTTON')}
                        {active > 0 && (
                            <>
                                <span aria-hidden="true" className="min-w-5 rounded-full bg-brand-100 px-1.5 text-xs font-semibold text-brand-600 tabular-nums">
                                    {active}
                                </span>
                                <span className="sr-only">
                                    {', '}
                                    {t('RESPONSES_STAFF.FILTERS_COUNT', { count: active })}
                                </span>
                            </>
                        )}
                    </Button>
                    <label className="flex items-center gap-2 text-sm text-black-700 sm:shrink-0" htmlFor={`${id}-sort`}>
                        <span className="whitespace-nowrap">{t(text.sort)}</span>
                        <select id={`${id}-sort`} className={cn(control, 'min-w-0 sm:w-auto')} value={state.sort} onChange={(event) => onChange({ sort: event.target.value as ResponseSort })}>
                            {SORTS.map((value) => (
                                <option key={value} value={value}>
                                    {t(SORT_LABEL[value])}
                                </option>
                            ))}
                        </select>
                    </label>
                </form>
                {trailing}
            </div>
            {open && (
                <div id={panelId} role="group" aria-label={t('RESPONSES_STAFF.FILTERS_PANEL')} className="grid grid-cols-1 gap-3 rounded border border-black-300 bg-white p-4 min-[480px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
                    <Field id={`${id}-from`} label={t(text.from)}>
                        <input id={`${id}-from`} type="date" className={control} value={state.from ?? ''} max={state.to} onChange={(event) => onChange({ from: event.target.value || undefined })} />
                    </Field>
                    <Field id={`${id}-to`} label={t(text.to)}>
                        <input id={`${id}-to`} type="date" className={control} value={state.to ?? ''} min={state.from} onChange={(event) => onChange({ to: event.target.value || undefined })} />
                    </Field>
                    <Field id={`${id}-who`} label={t(text.who)}>
                        <select id={`${id}-who`} className={control} value={state.who ?? ''} onChange={(event) => onChange({ who: (event.target.value || undefined) as ResponseListState['who'] })}>
                            <option value="">{t(text.whoAny)}</option>
                            {RESPONDENTS.map((value) => (
                                <option key={value} value={value}>
                                    {t(WHO_LABEL[value])}
                                </option>
                            ))}
                        </select>
                    </Field>
                    <Field id={`${id}-status`} label={t(text.status)}>
                        <select id={`${id}-status`} className={control} value={state.status ?? ''} onChange={(event) => onChange({ status: (event.target.value || undefined) as ResponseListState['status'] })}>
                            <option value="">{t(text.statusAny)}</option>
                            {DELETION_STATUSES.map((value) => (
                                <option key={value} value={value}>
                                    {t(STATUS_LABEL[value])}
                                </option>
                            ))}
                        </select>
                    </Field>
                    <Field id={`${id}-version`} label={t(text.version)}>
                        <select id={`${id}-version`} className={control} value={state.version ?? ''} onChange={(event) => onChange({ version: event.target.value ? Number(event.target.value) : undefined })}>
                            <option value="">{t(text.versionAny)}</option>
                            {versions.map((version) => (
                                <option key={version} value={version}>
                                    {versionLabel(version)}
                                </option>
                            ))}
                        </select>
                    </Field>
                </div>
            )}
            {chips.length > 0 && (
                <ul aria-label={t('RESPONSES_STAFF.ACTIVE_FILTERS')} className="flex flex-wrap items-center gap-2">
                    {chips.map((chip) => (
                        <li key={chip.key} className="flex items-center gap-1 rounded-full bg-brand-100 py-0.5 pr-1 pl-3 text-sm text-black-900">
                            <span>{chip.label}</span>
                            <button
                                type="button"
                                aria-label={t('RESPONSES_STAFF.REMOVE_FILTER', { filter: chip.label })}
                                className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-brand-200 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500"
                                onClick={() => {
                                    onChange(chip.remove);
                                    toggleRef.current?.focus();
                                }}
                            >
                                <X className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                    <li>
                        <button type="button" onClick={onClear} className="rounded text-sm font-medium text-brand-500 underline-offset-2 hover:underline focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500">
                            {t(text.clear)}
                        </button>
                    </li>
                </ul>
            )}
        </div>
    );
}
