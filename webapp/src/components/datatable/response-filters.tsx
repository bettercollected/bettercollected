import { useId } from 'react';

import { useTranslation } from 'react-i18next';

import { responsesListLocale as text } from '@app/constants/locales/responses-list';
import { cn } from '@app/shadcn/util/lib';
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
 * The filter bar of the responses list: submitted date range, deletion-request
 * state, anonymous or identified, form version, and the sort. Each control is
 * a native, labelled field (keyboard and screen reader ready); a change is
 * applied at once and lives in the URL (the parent writes it).
 */
export default function ResponseFilters({ state, currentVersion, onChange, onClear }: Props) {
    const { t } = useTranslation();
    const id = useId();
    const active = activeFilterCount(state);
    const versions = Array.from({ length: Math.min(Math.max(currentVersion ?? 1, state.version ?? 1), 200) }, (_, index) => index + 1).reverse();

    return (
        <form role="search" aria-label={t(text.filters)} className="mb-4 flex flex-col gap-3" onSubmit={(event) => event.preventDefault()}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
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
                                {t(version === currentVersion ? text.versionCurrent : text.versionN, { n: version })}
                            </option>
                        ))}
                    </select>
                </Field>
                <Field id={`${id}-sort`} label={t(text.sort)} className="col-span-2 md:col-span-1">
                    <select id={`${id}-sort`} className={control} value={state.sort} onChange={(event) => onChange({ sort: event.target.value as ResponseSort })}>
                        {SORTS.map((value) => (
                            <option key={value} value={value}>
                                {t(SORT_LABEL[value])}
                            </option>
                        ))}
                    </select>
                </Field>
            </div>
            {active > 0 && (
                <div>
                    <button type="button" onClick={onClear} className="text-brand-500 focus-visible:ring-brand-500 rounded text-sm font-medium underline-offset-2 hover:underline focus:outline-hidden focus-visible:ring-2">
                        {t(text.clear)}
                    </button>
                </div>
            )}
        </form>
    );
}
