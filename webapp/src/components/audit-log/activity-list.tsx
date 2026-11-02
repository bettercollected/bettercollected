'use client';

import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { ChevronDown, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { AUDIT_AREAS, AuditArea, AuditEntryDto, AuditLabels } from '@app/models/dtos/audit-log-dto';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { buttonClassName } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { WORKSPACE_PERMISSIONS_TAG, workspacesApi } from '@app/store/workspaces/api';
import { useLazyGetAuditLogQuery } from '@app/store/workspaces/audit-log-api';
import { useGetAuditRetentionQuery } from '@app/store/workspaces/audit-retention-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { formVersionsUrl, responsePageUrl, responsesListUrl } from '@app/utils/response-urls';

import { AuditFilters, EMPTY_FILTERS, activeFilterCount, auditQuery, filtersToSearch, hidesBreakGlass, parseFilters } from './filters';
import { AuditRetentionSetting } from './retention-setting';
import { describeEntry } from './sentences';

const PAGE_SIZE = 20;
const control = 'min-h-11 rounded border border-black-300 bg-white px-3 text-sm text-black-900 md:min-h-10';
const actionClass = buttonClassName({ variant: 'v2Button', size: 'sm', className: 'min-h-11 md:min-h-9' });

interface Loaded {
    entries: AuditEntryDto[];
    cursor: string | null;
    retentionDays?: number;
}

type View = ({ status: 'loading' } | { status: 'error' } | ({ status: 'ready' } & Loaded)) & { more?: 'loading' | 'error' };

const noLabels: AuditLabels = { members: {}, forms: {}, teams: {} };

/** The retention figure as a sentence: whole months when it is that, else days. */
function retentionText(t: (key: string, options?: Record<string, unknown>) => string, days: number): string {
    const months = Math.round(days / 30.4375);
    return days >= 60 ? t('AUDIT_LOG.RETENTION_MONTHS', { count: months }) : t('AUDIT_LOG.RETENTION_DAYS', { count: days });
}

/**
 * The workspace's activity (docs/audit-log.md), or one form's when `formId` is given: who changed what, newest first,
 * in plain sentences. Mounted only for someone who holds audit.read while the server's AUDIT_LOG_UI_ENABLED is on
 * (`ActivityGate`), so nothing is asked of the server otherwise. What each row shows follows what the server sent: a
 * session id or a response link is drawn only when it is there, never worked out here.
 */
export function ActivityList({ formId }: { formId?: string }) {
    const { t, i18n } = useTranslation();
    const locale = useIntlLocale();
    const router = useRouter();
    const pathname = usePathname() ?? '';
    const searchParams = useSearchParams();
    const workspace = useAppSelector(selectWorkspace);
    const { can, formRevisionsUiEnabled } = useWorkspacePermissions();
    // the trigger of the store's lazy query is stable between renders
    const [load] = useLazyGetAuditLogQuery();
    const workspaceId: string = workspace?.id ?? '';
    const workspaceName: string = workspace?.workspaceName ?? '';
    const filtersId = useId();
    // the workspace's own period (the form's page states the list's); it follows a change made on this page at once
    const { data: setting } = useGetAuditRetentionQuery(workspaceId, { skip: !workspaceId || !!formId });

    const search = searchParams?.toString() ?? '';
    const filters = useMemo(() => parseFilters(new URLSearchParams(search)), [search]);
    // a form's own page fixes the form; the Form filter does not exist there
    const effective: AuditFilters = formId ? { ...filters, form: undefined } : filters;
    const rangeInvalid = !!effective.from && !!effective.to && effective.from > effective.to;
    const query = auditQuery(effective, { limit: PAGE_SIZE }, formId ? undefined : effective.form);

    const [view, setView] = useState<View>({ status: 'loading' });
    // every label seen on any page, kept across filter changes: the pickers offer who and which forms the log has shown
    const [labels, setLabels] = useState<AuditLabels>(noLabels);
    const [announcement, setAnnouncement] = useState('');
    const [loadedOlder, setLoadedOlder] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const request = useRef(0);

    const mergeLabels = useCallback((incoming: Partial<AuditLabels> | undefined) => {
        if (!incoming) return;
        setLabels((previous) => ({
            members: { ...previous.members, ...(incoming.members ?? {}) },
            forms: { ...previous.forms, ...(incoming.forms ?? {}) },
            teams: { ...previous.teams, ...(incoming.teams ?? {}) }
        }));
    }, []);

    const first = useCallback(async () => {
        const mine = ++request.current;
        setLoadedOlder(false);
        setAnnouncement('');
        if (!workspaceId || rangeInvalid) {
            setView({ status: 'ready', entries: [], cursor: null });
            return;
        }
        setView({ status: 'loading' });
        try {
            const page = await load({ workspaceId, formId, query }, false).unwrap();
            if (mine !== request.current) return;
            mergeLabels(page.labels);
            setView({ status: 'ready', entries: page.entries ?? [], cursor: page.nextCursor ?? null, retentionDays: page.retentionDays });
        } catch {
            if (mine === request.current) setView({ status: 'error' });
        }
    }, [workspaceId, formId, query, rangeInvalid, load, mergeLabels]);

    // a changed filter, workspace or form starts the list again
    useEffect(() => {
        void first();
    }, [first]);

    const older = async () => {
        if (view.status !== 'ready' || !view.cursor || view.more === 'loading') return;
        const mine = request.current;
        const base = view;
        setView({ ...base, more: 'loading' });
        try {
            const page = await load({ workspaceId, formId, query: auditQuery(effective, { cursor: base.cursor, limit: PAGE_SIZE }, formId ? undefined : effective.form) }, false).unwrap();
            if (mine !== request.current) return;
            mergeLabels(page.labels);
            setLoadedOlder(true);
            setView({ status: 'ready', entries: [...base.entries, ...(page.entries ?? [])], cursor: page.nextCursor ?? null, retentionDays: page.retentionDays ?? base.retentionDays });
            setAnnouncement(page.entries?.length ? t('AUDIT_LOG.LOADED_MORE', { count: page.entries.length }) : '');
        } catch {
            if (mine === request.current) setView({ ...base, more: 'error' });
        }
    };

    const setFilters = (next: AuditFilters) => {
        const text = filtersToSearch(next);
        router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
    };

    const when = useMemo(() => new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }), [locale]);
    const day = useMemo(() => new Intl.DateTimeFormat(locale, { dateStyle: 'full' }), [locale]);
    // the date filters are UTC days: their chips name the same day wherever the viewer is
    const dayUtc = useMemo(() => new Intl.DateTimeFormat(locale, { dateStyle: 'full', timeZone: 'UTC' }), [locale]);
    const count = activeFilterCount(effective, !formId);
    const Heading = formId ? 'h3' : 'h2';

    // pickers: those the log has shown so far, plus the one the address names
    const people = Object.entries(labels.members)
        .filter(([, label]) => label.status === 'member' && label.name)
        .map(([id, label]) => ({ id, name: label.name as string }))
        .sort((a, b) => a.name.localeCompare(b.name, locale));
    const forms = Object.entries(labels.forms)
        .filter(([, label]) => label.status === 'available' && label.title)
        .map(([id, label]) => ({ id, title: label.title as string }))
        .sort((a, b) => a.title.localeCompare(b.title, locale));
    const personName = (id: string) => people.find((p) => p.id === id)?.name ?? t('AUDIT_LOG.NAME.FORMER_MEMBER');
    const formTitle = (id: string) => forms.find((f) => f.id === id)?.title ?? t('AUDIT_LOG.NAME.GONE');
    const dateText = (value: string) => dayUtc.format(new Date(`${value}T00:00:00Z`)).replace(/^./, (c) => c.toLocaleUpperCase(locale));

    const chips: Array<{ key: string; text: string; remove: () => void }> = [
        ...effective.areas.map((area) => ({ key: `area-${area}`, text: t('AUDIT_LOG.CHIP_AREA', { area: t(`AUDIT_LOG.AREA.${area}`) }), remove: () => setFilters({ ...effective, areas: effective.areas.filter((a) => a !== area) }) })),
        ...(effective.who ? [{ key: 'who', text: t(effective.about ? 'AUDIT_LOG.CHIP_WHO_ABOUT' : 'AUDIT_LOG.CHIP_WHO', { name: personName(effective.who) }), remove: () => setFilters({ ...effective, who: undefined, about: false }) }] : []),
        ...(!formId && effective.form ? [{ key: 'form', text: t('AUDIT_LOG.CHIP_FORM', { form: formTitle(effective.form) }), remove: () => setFilters({ ...effective, form: undefined }) }] : []),
        ...(effective.from ? [{ key: 'from', text: t('AUDIT_LOG.CHIP_FROM', { date: dateText(effective.from) }), remove: () => setFilters({ ...effective, from: undefined }) }] : []),
        ...(effective.to ? [{ key: 'to', text: t('AUDIT_LOG.CHIP_TO', { date: dateText(effective.to) }), remove: () => setFilters({ ...effective, to: undefined }) }] : [])
    ];

    const toggleArea = (area: AuditArea, on: boolean) => setFilters({ ...effective, areas: AUDIT_AREAS.filter((a) => (a === area ? on : effective.areas.includes(a))) });

    // entries grouped under day headings, in the order the server sent them
    const groups = useMemo(() => {
        if (view.status !== 'ready') return [];
        const today = new Date();
        const key = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
        const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
        const result: Array<{ key: string; label: string; entries: AuditEntryDto[] }> = [];
        for (const entry of view.entries) {
            const date = new Date(entry.at);
            const dayKey = Number.isNaN(date.getTime()) ? 'unknown' : key(date);
            let group = result[result.length - 1];
            if (!group || group.key !== dayKey) {
                const label = dayKey === 'unknown' ? '' : dayKey === key(today) ? t('AUDIT_LOG.TODAY') : dayKey === key(yesterday) ? t('AUDIT_LOG.YESTERDAY') : day.format(date).replace(/^./, (c) => c.toLocaleUpperCase(locale));
                group = { key: dayKey, label, entries: [] };
                result.push(group);
            }
            group.entries.push(entry);
        }
        return result;
        // `i18n.language` re-words the day names when the language changes
    }, [view, day, locale, i18n.language, t]);

    const retentionDays = setting?.days ?? (view.status === 'ready' ? view.retentionDays : undefined);
    const retention = view.status === 'ready' && typeof retentionDays === 'number' && retentionDays > 0 ? retentionText(t, retentionDays) : '';

    return (
        <div data-testid="activity-list" className="flex w-full max-w-[860px] flex-col gap-5 pb-10">
            <div className="flex flex-col gap-1">
                {formId ? (
                    <h2 id="activity-title" className="text-lg font-semibold">
                        {t('AUDIT_LOG.TITLE')}
                    </h2>
                ) : (
                    <h1 id="activity-title" className="sr-only">
                        {t('AUDIT_LOG.TITLE')}
                    </h1>
                )}
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">
                    {t(formId ? 'AUDIT_LOG.FORM_INTRO' : 'AUDIT_LOG.INTRO')} {retention}
                </p>
                {!formId && <AuditRetentionSetting workspaceId={workspaceId} />}
                {formId && (
                    <p className="text-sm">
                        <Link href={`/${workspaceName}/dashboard/activity?form=${encodeURIComponent(formId)}`} className="inline-flex min-h-11 items-center underline underline-offset-2 md:min-h-8">
                            {t('AUDIT_LOG.SEE_ALL')}
                        </Link>
                    </p>
                )}
            </div>

            <form role="search" aria-label={t('AUDIT_LOG.FILTERS')} className="flex flex-col gap-3" onSubmit={(event) => event.preventDefault()}>
                <button type="button" className={cn(actionClass, 'w-fit md:hidden')} aria-expanded={filtersOpen} aria-controls={filtersId} onClick={() => setFiltersOpen((open) => !open)}>
                    {count > 0 ? t('AUDIT_LOG.FILTERS_TOGGLE', { count }) : t('AUDIT_LOG.FILTERS_TOGGLE_NONE')}
                    <ChevronDown className={cn('ml-1 h-4 w-4 transition-transform', filtersOpen && 'rotate-180')} aria-hidden="true" />
                </button>
                <div id={filtersId} className={cn('flex-col gap-3 md:flex', filtersOpen ? 'flex' : 'hidden')}>
                    <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1">
                        <legend className="mb-1 text-xs font-medium text-black-700">{t('AUDIT_LOG.TYPE')}</legend>
                        {AUDIT_AREAS.map((area) => (
                            <label key={area} className="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-black-900 md:min-h-8">
                                <input type="checkbox" className="h-4 w-4" checked={effective.areas.includes(area)} onChange={(event) => toggleArea(area, event.target.checked)} />
                                {t(`AUDIT_LOG.AREA.${area}`)}
                            </label>
                        ))}
                    </fieldset>
                    <div className="flex flex-wrap items-end gap-3">
                        <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-xs font-medium text-black-700 md:flex-none">
                            {t('AUDIT_LOG.WHO')}
                            <select
                                className={control}
                                value={effective.who ?? ''}
                                onChange={(event) => setFilters({ ...effective, who: event.target.value || undefined, about: event.target.value ? effective.about : false })}
                            >
                                <option value="">{t('AUDIT_LOG.WHO_ANY')}</option>
                                {effective.who && !people.some((p) => p.id === effective.who) && <option value={effective.who}>{t('AUDIT_LOG.NAME.FORMER_MEMBER')}</option>}
                                {people.map((person) => (
                                    <option key={person.id} value={person.id}>
                                        {person.name}
                                    </option>
                                ))}
                            </select>
                        </label>
                        {effective.who && (
                            <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-xs font-medium text-black-700 md:flex-none">
                                {t('AUDIT_LOG.WHO_SCOPE')}
                                <select className={control} value={effective.about ? 'involving' : 'actor'} onChange={(event) => setFilters({ ...effective, about: event.target.value === 'involving' })}>
                                    <option value="actor">{t('AUDIT_LOG.WHO_SCOPE_ACTOR')}</option>
                                    <option value="involving">{t('AUDIT_LOG.WHO_SCOPE_INVOLVING')}</option>
                                </select>
                            </label>
                        )}
                        {!formId && (
                            <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-xs font-medium text-black-700 md:flex-none">
                                {t('AUDIT_LOG.FORM')}
                                <select className={control} value={effective.form ?? ''} onChange={(event) => setFilters({ ...effective, form: event.target.value || undefined })}>
                                    <option value="">{t('AUDIT_LOG.FORM_ANY')}</option>
                                    {effective.form && !forms.some((f) => f.id === effective.form) && <option value={effective.form}>{t('AUDIT_LOG.NAME.GONE')}</option>}
                                    {forms.map((form) => (
                                        <option key={form.id} value={form.id}>
                                            {form.title}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}
                        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-black-700 md:flex-none">
                            {t('AUDIT_LOG.FROM')}
                            <input type="date" className={control} value={effective.from ?? ''} max={effective.to || undefined} onChange={(event) => setFilters({ ...effective, from: event.target.value || undefined })} />
                        </label>
                        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-black-700 md:flex-none">
                            {t('AUDIT_LOG.TO')}
                            <input type="date" className={control} value={effective.to ?? ''} min={effective.from || undefined} onChange={(event) => setFilters({ ...effective, to: event.target.value || undefined })} />
                        </label>
                        {count > 0 && (
                            <button type="button" className={actionClass} onClick={() => setFilters(EMPTY_FILTERS)}>
                                {t('AUDIT_LOG.CLEAR')}
                            </button>
                        )}
                    </div>
                </div>
            </form>

            {chips.length > 0 && (
                <ul aria-label={t('AUDIT_LOG.CHIPS')} className="flex flex-wrap gap-2">
                    {chips.map((chip) => (
                        <li key={chip.key}>
                            <button type="button" aria-label={t('AUDIT_LOG.CHIP_REMOVE', { filter: chip.text })} onClick={chip.remove} className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-black-300 bg-white px-3 text-sm text-black-900 hover:bg-black-100 md:min-h-8">
                                {chip.text}
                                <X className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            {!formId && hidesBreakGlass(effective) && (
                <p className="flex flex-wrap items-center gap-x-2 text-sm text-black-700">
                    {t('AUDIT_LOG.BREAK_GLASS_HIDDEN')}
                    <button type="button" className="min-h-11 underline underline-offset-2 md:min-h-8" onClick={() => setFilters({ ...effective, areas: ['security'] })}>
                        {t('AUDIT_LOG.BREAK_GLASS_SHOW')}
                    </button>
                </p>
            )}

            {/* what a screen reader hears when older entries arrive: no focus moves */}
            <div role="status" aria-live="polite" className="sr-only" data-testid="activity-announcer">
                {announcement}
            </div>

            {rangeInvalid ? (
                <p role="alert" className="text-sm text-red-700">
                    {t('AUDIT_LOG.RANGE_INVALID')}
                </p>
            ) : view.status === 'loading' ? (
                <p role="status" className="text-sm text-black-700">
                    {t('AUDIT_LOG.LOADING')}
                </p>
            ) : view.status === 'error' ? (
                <div role="alert" className="flex flex-wrap items-center gap-3 rounded border border-black-300 bg-white p-4 text-sm">
                    <span>{t('AUDIT_LOG.LOAD_ERROR')}</span>
                    <button type="button" className={actionClass} onClick={() => void first()}>
                        {t('AUDIT_LOG.RETRY')}
                    </button>
                </div>
            ) : view.entries.length === 0 ? (
                <div className="flex flex-col items-start gap-3 rounded-lg border border-dashed border-black-400 p-6 text-sm text-black-700">
                    <p>{count > 0 ? t('AUDIT_LOG.EMPTY_FILTERED') : t('AUDIT_LOG.EMPTY_NONE')}</p>
                    {count > 0 && (
                        <button type="button" className={actionClass} onClick={() => setFilters(EMPTY_FILTERS)}>
                            {t('AUDIT_LOG.CLEAR')}
                        </button>
                    )}
                </div>
            ) : (
                <div className="flex flex-col gap-5">
                    {groups.map((group, index) => (
                        <section key={`${group.key}-${index}`} aria-labelledby={`${filtersId}-day-${index}`} className="flex flex-col gap-2">
                            {group.label && (
                                <Heading id={`${filtersId}-day-${index}`} className="text-sm font-semibold text-black-800">
                                    {group.label}
                                </Heading>
                            )}
                            <ol aria-label={group.label ? undefined : t('AUDIT_LOG.LIST')} className="flex flex-col divide-y divide-black-200 rounded border border-black-200 bg-white">
                                {group.entries.map((entry) => {
                                    const sentence = describeEntry(entry, { labels, t, formId });
                                    const date = new Date(entry.at);
                                    const valid = !Number.isNaN(date.getTime());
                                    const area = entry.area && (AUDIT_AREAS as readonly string[]).includes(entry.area) ? t(`AUDIT_LOG.AREA.${entry.area}`) : '';
                                    return (
                                        <li key={entry.id} className="flex flex-col gap-1 p-3 text-sm text-black-900 sm:flex-row sm:gap-4">
                                            <div className="flex shrink-0 items-center gap-2 text-xs text-black-700 sm:w-28 sm:flex-col sm:items-start sm:gap-1">
                                                {valid && (
                                                    <time dateTime={entry.at} title={date.toISOString()}>
                                                        {when.format(date)}
                                                    </time>
                                                )}
                                                {area && <span className="rounded bg-black-100 px-1.5 py-0.5 text-[11px] font-medium text-black-800">{area}</span>}
                                            </div>
                                            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                                                <p className="break-words leading-relaxed">
                                                    {sentence.segments.map((segment, i) => (segment.strong ? <strong key={i}>{segment.text}</strong> : <React.Fragment key={i}>{segment.text}</React.Fragment>))}
                                                </p>
                                                {entry.method && entry.path && (
                                                    <code className="break-all text-[11px] text-black-700">
                                                        {entry.method} {entry.path}
                                                    </code>
                                                )}
                                                {entry.sessionId && <span className="break-all text-xs text-black-700">{t('AUDIT_LOG.SESSION', { id: entry.sessionId })}</span>}
                                                {entry.responseId && entry.formId && (
                                                    <Link
                                                        href={responsePageUrl(workspaceName, entry.formId, entry.responseId)}
                                                        className={cn(actionClass, 'w-fit')}
                                                        aria-label={valid ? t('AUDIT_LOG.OPEN_RESPONSE_AT', { time: `${day.format(date)} ${when.format(date)}` }) : undefined}
                                                    >
                                                        {t('AUDIT_LOG.OPEN_RESPONSE')}
                                                    </Link>
                                                )}
                                            </div>
                                        </li>
                                    );
                                })}
                            </ol>
                        </section>
                    ))}

                    {view.more === 'error' && (
                        <p role="alert" className="text-sm text-red-700">
                            {t('AUDIT_LOG.LOAD_MORE_ERROR')}
                        </p>
                    )}
                    {(view.cursor || loadedOlder) && (
                        <button type="button" className={cn(actionClass, 'w-fit')} aria-disabled={!view.cursor || view.more === 'loading'} onClick={() => void older()}>
                            {view.cursor ? t('AUDIT_LOG.SHOW_OLDER') : t('AUDIT_LOG.NO_OLDER')}
                        </button>
                    )}
                </div>
            )}

            {formId && (
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-black-700">
                    <span>{t('AUDIT_LOG.ELSEWHERE')}</span>
                    {formRevisionsUiEnabled && can(WorkspacePermission.FORM_READ) && (
                        <Link href={formVersionsUrl(workspaceName, formId)} className="inline-flex min-h-11 items-center underline underline-offset-2 md:min-h-8">
                            {t('AUDIT_LOG.LINK_VERSIONS')}
                        </Link>
                    )}
                    {can(WorkspacePermission.FORM_EDIT) && (
                        <Link href={`/${workspaceName}/dashboard/forms/${formId}/settings/automations`} className="inline-flex min-h-11 items-center underline underline-offset-2 md:min-h-8">
                            {t('AUDIT_LOG.LINK_DELIVERIES')}
                        </Link>
                    )}
                    {can(WorkspacePermission.RESPONSE_READ) && (
                        <Link href={responsesListUrl(workspaceName, formId)} className="inline-flex min-h-11 items-center underline underline-offset-2 md:min-h-8">
                            {t('AUDIT_LOG.LINK_RESPONSES')}
                        </Link>
                    )}
                </p>
            )}
        </div>
    );
}

/**
 * The gate of both Activity pages: nothing is drawn or asked for until the permissions have arrived; while the server's
 * switch is off a direct visit goes back to the forms list; without audit.read the page says so (the API refuses too).
 */
export function ActivityGate({ formId }: { formId?: string }) {
    const { t } = useTranslation();
    const router = useRouter();
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const { ready, answered, can, auditLogUiEnabled } = useWorkspacePermissions();
    const workspaceName: string = workspace?.workspaceName ?? '';
    const off = ready && answered && !auditLogUiEnabled;

    useEffect(() => {
        if (off && workspaceName) router.replace(`/${workspaceName}/dashboard/forms`);
    }, [off, workspaceName, router]);

    if (!ready) return <div role="status" aria-live="polite" />;
    if (off) return null;
    // the permissions request failed: that proves nothing about the viewer's rights, so say so and let them try again
    if (!answered) {
        return (
            <div role="alert" className="flex max-w-2xl flex-wrap items-center gap-3 rounded border border-black-300 bg-white p-4 text-sm">
                <span>{t('AUDIT_LOG.PERMISSIONS_ERROR')}</span>
                <button type="button" className={actionClass} onClick={() => dispatch(workspacesApi.util.invalidateTags([WORKSPACE_PERMISSIONS_TAG]))}>
                    {t('AUDIT_LOG.RETRY')}
                </button>
            </div>
        );
    }
    if (!can(WorkspacePermission.AUDIT_READ)) {
        return (
            <p role="status" className="max-w-2xl text-sm text-black-700">
                {t('AUDIT_LOG.NO_ACCESS')}
            </p>
        );
    }
    return <ActivityList formId={formId} />;
}
