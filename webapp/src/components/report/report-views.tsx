'use client';

/**
 * The views bar of the Report page: open a saved view, save the report on screen as one (for the
 * member alone, or for everyone who can open the report when they may edit the form), update,
 * rename, share or delete it. A view is a name, a scope and the report's definition (question
 * ids, enums, dates; never an answer): opening one writes its cards and filters into the address,
 * which stays the one place the report lives (`report-page.tsx`).
 */
import React, { useEffect, useId, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useCreateReportViewMutation, useDeleteReportViewMutation, useUpdateReportViewMutation } from '@app/store/workspaces/api';
import { ReportDefinition, ReportView, ReportViewList, ReportViewScope, reportErrorOf } from '@app/utils/report';

const control = 'border-black-300 text-black-900 focus-visible:ring-brand-500 h-10 w-full rounded border bg-white py-0 pr-9 pl-3 text-sm text-ellipsis focus:outline-hidden focus-visible:ring-2';

type Panel = 'save' | 'details' | 'delete' | null;

interface Props {
    workspaceId: string;
    formId: string;
    list?: ReportViewList;
    loading?: boolean;
    failed?: boolean;
    /** The saved view the address names, when there is one. */
    current?: ReportView;
    /** The report on screen is not what the current view stored. */
    modified: boolean;
    /** The definition of the report on screen: what a save stores. */
    definition: ReportDefinition;
    /** There is something to save (at least one card the server can answer). */
    canSave: boolean;
    /** Cards of the report on screen that this person cannot have answered (a question they may not see): a view they
     *  update would lose them, so "Update" is not offered, only a save as a new view. */
    hiddenCards?: number;
    /** Open a view (its cards and filters become the report) or, with null, go back to the Overview. */
    onOpen: (view: ReportView | null) => void;
    /** Mark a view as the one on screen, without changing the report (after a save). */
    onMark: (view: ReportView | null) => void;
    onReload: () => void;
}

/** What a refusal of a view request says, in the viewer's language. */
export function viewErrorText(code: string | undefined, status: number | undefined, t: (key: string) => string): string {
    if (code === 'view_name_taken') return t('REPORT.VIEW_NAME_TAKEN');
    if (code === 'view_limit') return t('REPORT.VIEW_LIMIT');
    if (code === 'view_changed') return t('REPORT.VIEW_CHANGED');
    if (code === 'op_not_allowed') return t('REPORT.VIEW_NEEDS_NO_CONDITION');
    if (code === 'view_not_found' || status === 404) return t('REPORT.VIEW_NOT_FOUND');
    if (code === 'view_forbidden' || status === 403) return t('REPORT.VIEW_FORBIDDEN');
    if (code === 'invalid_view' || status === 422) return t('REPORT.VIEW_INVALID');
    return t('REPORT.VIEW_ERROR');
}

export default function ReportViews({ workspaceId, formId, list, loading, failed, current, modified, definition, canSave, hiddenCards = 0, onOpen, onMark, onReload }: Props) {
    const { t } = useTranslation();
    const id = useId();
    const [panel, setPanel] = useState<Panel>(null);
    const [name, setName] = useState('');
    const [scope, setScope] = useState<ReportViewScope>('private');
    const [problem, setProblem] = useState<{ code?: string; status?: number } | undefined>();
    const [notice, setNotice] = useState('');
    const nameRef = useRef<HTMLInputElement>(null);
    const saveRef = useRef<HTMLButtonElement>(null);
    const detailsRef = useRef<HTMLButtonElement>(null);
    const deleteRef = useRef<HTMLButtonElement>(null);
    const [create, creating] = useCreateReportViewMutation();
    const [update, updating] = useUpdateReportViewMutation();
    const [remove, removing] = useDeleteReportViewMutation();
    const busy = creating.isLoading || updating.isLoading || removing.isLoading;
    const views = list?.views ?? [];
    const mine = views.filter((view) => view.scope === 'private');
    const shared = views.filter((view) => view.scope === 'form');
    const canShare = !!list?.canShare;

    // opening a panel moves focus into it; closing one gives focus back to its button
    useEffect(() => {
        if (panel === 'save' || panel === 'details') nameRef.current?.focus();
    }, [panel]);

    const close = (back?: React.RefObject<HTMLButtonElement | null>) => {
        setPanel(null);
        setProblem(undefined);
        back?.current?.focus();
    };
    const openPanel = (next: Exclude<Panel, null>) => {
        setProblem(undefined);
        setNotice('');
        if (next === 'save') {
            setName('');
            setScope('private');
        } else if (next === 'details' && current) {
            setName(current.name);
            setScope(current.scope);
        }
        setPanel(next);
    };
    const fail = (error: unknown) => {
        const found = reportErrorOf(error);
        setProblem({ code: found.code, status: found.status });
        if (found.code === 'view_changed') onReload();
    };
    // a person who may not share saves privately, whatever the radio held
    const chosenScope: ReportViewScope = canShare ? scope : 'private';

    const submitSave = async (event: React.FormEvent) => {
        event.preventDefault();
        setProblem(undefined);
        try {
            const view = await create({ workspaceId, formId, name, scope: chosenScope, definition }).unwrap();
            setNotice(t('REPORT.VIEW_SAVED'));
            onMark(view);
            close(saveRef);
        } catch (error) {
            fail(error);
        }
    };
    const submitDetails = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!current) return;
        setProblem(undefined);
        try {
            const changes: { name?: string; scope?: ReportViewScope } = {};
            if (name.trim() !== current.name) changes.name = name;
            if (chosenScope !== current.scope) changes.scope = chosenScope;
            if (Object.keys(changes).length) await update({ workspaceId, formId, viewId: current.id, revision: current.revision, ...changes }).unwrap();
            setNotice(t('REPORT.VIEW_SAVED'));
            close(detailsRef);
        } catch (error) {
            fail(error);
        }
    };
    const submitUpdate = async () => {
        if (!current) return;
        setProblem(undefined);
        try {
            await update({ workspaceId, formId, viewId: current.id, revision: current.revision, definition }).unwrap();
            setNotice(t('REPORT.VIEW_UPDATED'));
        } catch (error) {
            fail(error);
            setPanel(null);
        }
    };
    const submitDelete = async () => {
        if (!current) return;
        setProblem(undefined);
        try {
            await remove({ workspaceId, formId, viewId: current.id, revision: current.revision }).unwrap();
            setNotice(t('REPORT.VIEW_DELETED'));
            onMark(null);
            close(saveRef);
        } catch (error) {
            fail(error);
        }
    };

    const owner = current && current.scope === 'form' ? (current.mine ? t('REPORT.VIEW_MADE_BY_YOU') : current.ownerName ? t('REPORT.VIEW_MADE_BY', { name: current.ownerName }) : t('REPORT.VIEW_FORMER_OWNER')) : undefined;
    const errorText = problem ? viewErrorText(problem.code, problem.status, t) : '';

    return (
        <section aria-label={t('REPORT.VIEWS')} className="flex flex-col gap-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
                <div className="flex min-w-0 flex-col gap-1 sm:w-72">
                    <label htmlFor={`${id}-views`} className="p4-new text-black-700">
                        {t('REPORT.VIEWS')}
                    </label>
                    <select
                        id={`${id}-views`}
                        className={control}
                        value={current?.id ?? ''}
                        disabled={loading && !list}
                        onChange={(event) => {
                            setPanel(null);
                            setNotice('');
                            onOpen(views.find((view) => view.id === event.target.value) ?? null);
                        }}
                    >
                        <option value="">{t('REPORT.OVERVIEW')}</option>
                        {mine.length > 0 && (
                            <optgroup label={t('REPORT.VIEW_GROUP_MINE')}>
                                {mine.map((view) => (
                                    <option key={view.id} value={view.id}>
                                        {view.name}
                                    </option>
                                ))}
                            </optgroup>
                        )}
                        {shared.length > 0 && (
                            <optgroup label={t('REPORT.VIEW_GROUP_SHARED')}>
                                {shared.map((view) => (
                                    <option key={view.id} value={view.id}>
                                        {view.name}
                                    </option>
                                ))}
                            </optgroup>
                        )}
                    </select>
                </div>
                <div className="flex flex-wrap gap-2">
                    {canSave && (
                        <Button ref={saveRef} type="button" variant="v2Button" className="h-10 px-4" aria-expanded={panel === 'save'} onClick={() => (panel === 'save' ? close(saveRef) : openPanel('save'))}>
                            {current ? t('REPORT.VIEW_SAVE_AS') : t('REPORT.VIEW_SAVE')}
                        </Button>
                    )}
                    {current && modified && current.canEdit && (
                        <Button type="button" variant="primary" className="h-10 px-4" disabled={busy || hiddenCards > 0} aria-describedby={hiddenCards > 0 ? `${id}-blocked` : undefined} onClick={submitUpdate}>
                            {t('REPORT.VIEW_UPDATE')}
                        </Button>
                    )}
                    {current?.canEdit && (
                        <Button ref={detailsRef} type="button" variant="v2Button" className="h-10 px-4" aria-expanded={panel === 'details'} onClick={() => (panel === 'details' ? close(detailsRef) : openPanel('details'))}>
                            {t('REPORT.VIEW_DETAILS')}
                        </Button>
                    )}
                    {current?.canDelete && (
                        <Button ref={deleteRef} type="button" variant="v2Button" className="h-10 px-4" aria-expanded={panel === 'delete'} onClick={() => (panel === 'delete' ? close(deleteRef) : openPanel('delete'))}>
                            {t('REPORT.VIEW_DELETE')}
                        </Button>
                    )}
                </div>
            </div>

            {current && (
                <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-black-700">
                    <span>{current.scope === 'form' ? t('REPORT.VIEW_SHARED') : t('REPORT.VIEW_PRIVATE')}</span>
                    {owner && <span>{owner}</span>}
                    {modified && <span className="font-medium text-black-900">{t('REPORT.VIEW_MODIFIED')}</span>}
                </p>
            )}
            {current && modified && current.canEdit && hiddenCards > 0 && (
                <p id={`${id}-blocked`} className="m-0 max-w-xl text-sm text-black-800">
                    {t('REPORT.VIEW_UPDATE_BLOCKED', { count: hiddenCards })}
                </p>
            )}
            {failed && (
                <p role="alert" className="m-0 text-sm text-black-800">
                    {t('REPORT.VIEWS_ERROR')}
                </p>
            )}
            <p role="status" aria-live="polite" className={cn('m-0 text-sm text-black-700', !notice && 'sr-only')}>
                {notice}
            </p>

            {(panel === 'save' || panel === 'details') && (
                <form
                    aria-label={panel === 'save' ? t('REPORT.VIEW_SAVE') : t('REPORT.VIEW_DETAILS')}
                    onSubmit={panel === 'save' ? submitSave : submitDetails}
                    onKeyDown={(event) => {
                        if (event.key === 'Escape') close(panel === 'save' ? saveRef : detailsRef);
                    }}
                    className="flex max-w-xl flex-col gap-3 rounded border border-black-300 bg-white p-4"
                >
                    <div className="flex flex-col gap-1">
                        <label htmlFor={`${id}-name`} className="p4-new text-black-700">
                            {t('REPORT.VIEW_NAME')}
                        </label>
                        <input ref={nameRef} id={`${id}-name`} type="text" required maxLength={list?.limits.nameMax ?? 80} value={name} onChange={(event) => setName(event.target.value)} className={cn(control, 'pr-3')} />
                    </div>
                    <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
                        <legend className="p4-new mb-1 text-black-700">{t('REPORT.VIEW_WHO')}</legend>
                        <label className="flex items-center gap-2 text-sm text-black-900">
                            <input type="radio" name={`${id}-scope`} checked={chosenScope === 'private'} onChange={() => setScope('private')} />
                            {t('REPORT.VIEW_PRIVATE_CHOICE')}
                        </label>
                        <label className={cn('flex items-center gap-2 text-sm', canShare ? 'text-black-900' : 'text-black-600')}>
                            <input type="radio" name={`${id}-scope`} checked={chosenScope === 'form'} disabled={!canShare} onChange={() => setScope('form')} aria-describedby={`${id}-help`} />
                            {t('REPORT.VIEW_SHARED_CHOICE')}
                        </label>
                        <p id={`${id}-help`} className="m-0 text-xs text-black-600">
                            {canShare ? t('REPORT.VIEW_SHARED_HELP') : t('REPORT.VIEW_SHARED_NEEDS_EDIT')}
                        </p>
                    </fieldset>
                    {errorText && (
                        <p role="alert" className="m-0 text-sm text-black-900">
                            {errorText}
                        </p>
                    )}
                    <div className="flex gap-2">
                        <Button type="submit" variant="primary" className="h-10 px-4" disabled={busy || !name.trim()}>
                            {panel === 'save' ? t('REPORT.VIEW_SAVE') : t('REPORT.DONE')}
                        </Button>
                        <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => close(panel === 'save' ? saveRef : detailsRef)}>
                            {t('REPORT.CANCEL')}
                        </Button>
                    </div>
                </form>
            )}

            {panel === 'delete' && current && (
                <div
                    role="group"
                    aria-label={t('REPORT.VIEW_DELETE')}
                    onKeyDown={(event) => {
                        if (event.key === 'Escape') close(deleteRef);
                    }}
                    className="flex max-w-xl flex-col gap-3 rounded border border-black-300 bg-white p-4"
                >
                    <p className="m-0 text-sm text-black-900">{t('REPORT.VIEW_DELETE_CONFIRM', { name: current.name })}</p>
                    {current.scope === 'form' && <p className="m-0 text-xs text-black-600">{t('REPORT.VIEW_DELETE_SHARED')}</p>}
                    {errorText && (
                        <p role="alert" className="m-0 text-sm text-black-900">
                            {errorText}
                        </p>
                    )}
                    <div className="flex gap-2">
                        <Button type="button" variant="primary" className="h-10 px-4" disabled={busy} onClick={submitDelete}>
                            {t('REPORT.VIEW_DELETE')}
                        </Button>
                        <Button type="button" variant="v2Button" className="h-10 px-4" onClick={() => close(deleteRef)}>
                            {t('REPORT.CANCEL')}
                        </Button>
                    </div>
                </div>
            )}
            {panel === null && errorText && (
                <p role="alert" className="m-0 text-sm text-black-900">
                    {errorText}
                </p>
            )}
        </section>
    );
}
