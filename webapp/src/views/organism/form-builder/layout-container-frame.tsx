'use client';

import { ReactNode, useId, useState } from 'react';

import cn from 'classnames';
import { useSetAtom } from 'jotai';
import { ArrowLeft, ArrowRight, ChevronDown, Plus, Trash2, Ungroup } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useLayoutContainerActions } from '@app/lib/hooks/use-layout-containers';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import type { LayoutContainer, LayoutTab, StandardFormFieldDto } from '@app/models/dtos/form';
import { activeContainerAtom, activeFieldAtom } from '@app/store/jotai/active-builder-component';
import { TABS_MAX } from '@app/utils/layout-containers';

const kindName = (t: (key: string) => string, container: LayoutContainer) => t(container.type === 'tabs' ? 'LAYOUT.TABS' : container.type === 'fieldset' ? 'LAYOUT.FIELDSET' : 'LAYOUT.PANEL');

/**
 * A title the creator types. It is saved as it is typed (one undo step per
 * burst) while it is not blank; a blank title is never stored (a panel,
 * field set and tab need one for their accessible name), so the stored title
 * comes back when the box is left empty.
 */
function TitleInput({ value, label, onCommit, disabled }: { value: string; label: string; onCommit: (title: string) => void; disabled?: boolean }) {
    const { t } = useTranslation('builder');
    const [draft, setDraft] = useState(value);
    const needed = useId();
    // the stored title came back changed (undo, another edit): show it
    const [shown, setShown] = useState(value);
    if (shown !== value) {
        setShown(value);
        setDraft(value);
    }
    const blank = !draft.trim();
    return (
        <span className="flex min-w-0 flex-1 flex-col">
            <input
                type="text"
                value={draft}
                disabled={disabled}
                maxLength={120}
                aria-label={label}
                aria-invalid={blank}
                aria-describedby={blank ? needed : undefined}
                onChange={(event) => {
                    setDraft(event.target.value);
                    if (event.target.value.trim()) onCommit(event.target.value);
                }}
                onBlur={() => blank && setDraft(value)}
                onClick={(event) => event.stopPropagation()}
                className="w-full min-w-0 rounded border border-black-300 bg-white px-2 py-1 text-sm font-semibold outline-hidden focus:border-brand-500"
            />
            {blank && (
                <span id={needed} className="text-[11px] text-[#B42318]">
                    {t('LAYOUT.TITLE_NEEDED')}
                </span>
            )}
        </span>
    );
}

const iconButton = 'text-black-700 hover:bg-black-100 focus-visible:ring-brand-500 inline-flex h-8 w-8 items-center justify-center rounded focus-visible:ring-2 focus-visible:outline-hidden disabled:cursor-not-allowed disabled:opacity-40';
const textButton = 'text-brand-500 hover:text-brand-600 focus-visible:ring-brand-500 inline-flex items-center gap-1 rounded px-1 py-1 text-xs font-medium focus-visible:ring-2 focus-visible:outline-hidden';

/**
 * A layout container on the builder's canvas: a frame around the run of
 * questions it holds, with its own controls (title, closed-by-default,
 * tabs, add a question, ungroup). Selecting its bar opens its visibility
 * settings in the inspector. A preview (`editable` false) shows the frame
 * and its title only.
 */
export default function LayoutContainerFrame({
    page,
    container,
    members,
    editable,
    renderMembers
}: {
    page: StandardFormFieldDto;
    container: LayoutContainer;
    /** The question ids in the container, in page order. */
    members: string[];
    editable: boolean;
    renderMembers: (ids: string[]) => ReactNode;
}) {
    const { t } = useTranslation('builder');
    const actions = useLayoutContainerActions();
    const { layoutContainersEnabled } = useWorkspacePermissions();
    const selectContainer = useSetAtom(activeContainerAtom);
    const selectField = useSetAtom(activeFieldAtom);
    // While the server does not take layout containers, what exists can lose questions or go, not change.
    const canChange = editable && layoutContainersEnabled;
    const kind = kindName(t, container);
    const select = () => {
        selectField(null);
        selectContainer({ pageId: page.id, id: container.id });
    };
    const rename = (title: string) => actions.update(page.id, container.id, { title }, 'Edit title', `container-title-${container.id}`);
    const label = `${kind}: ${container.title ?? ''}`.trim();

    return (
        <section aria-label={container.type === 'tabs' ? kind : label} data-canvas-container={container.id} className="w-full min-w-0 rounded-lg border border-dashed border-black-400 bg-white/40">
            {editable ? (
                <div className="flex flex-wrap items-center gap-2 border-b border-dashed border-black-300 px-3 py-2">
                    <button
                        type="button"
                        onClick={select}
                        className="flex shrink-0 items-center gap-1 rounded text-[11px] font-semibold tracking-wide text-black-700 uppercase hover:text-black-900 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                        aria-label={t('LAYOUT.VISIBILITY') + ': ' + kind}
                    >
                        {container.type === 'panel' && <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />}
                        {kind}
                        {container.logic && <span className="rounded bg-brand-100 px-1 py-px text-brand-500 normal-case">{t('LAYOUT.VISIBILITY')}</span>}
                    </button>
                    {container.type !== 'tabs' && <TitleInput value={container.title ?? ''} label={t('LAYOUT.TITLE_LABEL') + ' ' + kind} onCommit={rename} disabled={!canChange} />}
                    {container.type === 'tabs' && <span className="flex-1" />}
                    {container.type === 'panel' && (
                        <label className="flex items-center gap-1.5 text-xs text-black-700">
                            <input
                                type="checkbox"
                                checked={!!container.collapsed}
                                disabled={!canChange}
                                onChange={(event) => actions.update(page.id, container.id, (c) => ({ ...c, collapsed: event.target.checked ? true : undefined }), 'Edit panel')}
                                className="h-4 w-4"
                            />
                            {t('LAYOUT.COLLAPSED')}
                        </label>
                    )}
                    <button type="button" className={iconButton} aria-label={t('LAYOUT.UNGROUP_LABEL', { title: container.title ?? kind })} title={t('LAYOUT.UNGROUP')} onClick={() => actions.ungroup(page.id, container.id)}>
                        <Ungroup className="h-4 w-4" aria-hidden="true" />
                    </button>
                </div>
            ) : (
                <div className="px-3 py-1.5 text-xs font-semibold text-black-700">{container.type === 'tabs' ? kind : container.title}</div>
            )}
            <div className="flex flex-col gap-6 p-3">
                {container.type === 'tabs' ? (
                    <>
                        {(container.tabs?.length ?? 0) < 2 && editable && <p className="text-xs text-black-600">{t('LAYOUT.ONE_TAB')}</p>}
                        {(container.tabs ?? []).map((tab, index) => (
                            <TabGroup key={tab.id} page={page} container={container} tab={tab} index={index} count={container.tabs?.length ?? 0} editable={editable} canChange={canChange} renderMembers={renderMembers} />
                        ))}
                        {editable && (container.tabs?.length ?? 0) < TABS_MAX && (
                            <button type="button" disabled={!canChange} className={cn(textButton, 'w-fit disabled:opacity-40')} onClick={() => actions.addTab(page.id, container.id, t('LAYOUT.DEFAULT_TAB', { n: (container.tabs?.length ?? 0) + 1 }))}>
                                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                                {t('LAYOUT.ADD_TAB')}
                            </button>
                        )}
                    </>
                ) : (
                    <>
                        <div className="flex flex-col gap-12 @min-[448px]/page:grid @min-[448px]/page:grid-cols-12 @min-[448px]/page:gap-x-6 @min-[448px]/page:gap-y-12">{renderMembers(members)}</div>
                        {editable && (
                            <button
                                type="button"
                                disabled={!canChange}
                                className={cn(textButton, 'w-fit disabled:opacity-40')}
                                aria-label={t('LAYOUT.ADD_QUESTION_TO', { title: container.title ?? kind })}
                                onClick={() => actions.addQuestion(page.id, container.id)}
                            >
                                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                                {t('LAYOUT.ADD_QUESTION')}
                            </button>
                        )}
                    </>
                )}
            </div>
        </section>
    );
}

function TabGroup({
    page,
    container,
    tab,
    index,
    count,
    editable,
    canChange,
    renderMembers
}: {
    page: StandardFormFieldDto;
    container: LayoutContainer;
    tab: LayoutTab;
    index: number;
    count: number;
    editable: boolean;
    canChange: boolean;
    renderMembers: (ids: string[]) => ReactNode;
}) {
    const { t } = useTranslation('builder');
    const actions = useLayoutContainerActions();
    const ids = tab.fields ?? [];
    const rename = (title: string) => actions.update(page.id, container.id, (c) => ({ ...c, tabs: (c.tabs ?? []).map((entry) => (entry.id === tab.id ? { ...entry, title } : entry)) }), 'Edit tab', `tab-title-${tab.id}`);
    return (
        <div role="group" aria-label={tab.title} data-canvas-tab={tab.id} className="flex flex-col gap-4">
            {editable ? (
                <div className="flex items-center gap-1 border-b border-black-300 pb-1.5">
                    <TitleInput value={tab.title} label={t('LAYOUT.TAB_TITLE') + ' ' + (index + 1)} onCommit={rename} disabled={!canChange} />
                    <button type="button" className={iconButton} disabled={!canChange || index === 0} aria-label={t('LAYOUT.MOVE_TAB_LEFT')} title={t('LAYOUT.MOVE_TAB_LEFT')} onClick={() => actions.moveTab(page.id, container.id, tab.id, -1)}>
                        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <button type="button" className={iconButton} disabled={!canChange || index === count - 1} aria-label={t('LAYOUT.MOVE_TAB_RIGHT')} title={t('LAYOUT.MOVE_TAB_RIGHT')} onClick={() => actions.moveTab(page.id, container.id, tab.id, 1)}>
                        <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <button
                        type="button"
                        className={iconButton}
                        disabled={!canChange || count < 2}
                        aria-label={t('LAYOUT.REMOVE_TAB_LABEL', { title: tab.title })}
                        title={t('LAYOUT.REMOVE_TAB')}
                        onClick={() => actions.removeTab(page.id, container.id, tab.id)}
                    >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                </div>
            ) : (
                <div className="text-sm font-semibold text-black-700">{tab.title}</div>
            )}
            {ids.length ? (
                <div className="flex flex-col gap-12 @min-[448px]/page:grid @min-[448px]/page:grid-cols-12 @min-[448px]/page:gap-x-6 @min-[448px]/page:gap-y-12">{renderMembers(ids)}</div>
            ) : (
                editable && <p className="text-xs text-black-600">{t('LAYOUT.EMPTY_TAB')}</p>
            )}
            {editable && (
                <button type="button" disabled={!canChange} className={cn(textButton, 'w-fit disabled:opacity-40')} aria-label={t('LAYOUT.ADD_QUESTION_TO', { title: tab.title })} onClick={() => actions.addQuestion(page.id, container.id, tab.id)}>
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('LAYOUT.ADD_QUESTION')}
                </button>
            )}
        </div>
    );
}
