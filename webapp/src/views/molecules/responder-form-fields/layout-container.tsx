'use client';

import { KeyboardEvent, ReactNode, useRef } from 'react';

import cn from 'classnames';
import { ChevronDown } from 'lucide-react';

import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import type { LayoutContainer, LayoutTab, StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useContainerView, useSetContainerView } from '@app/store/jotai/responder-layout-state';
import { memberIdOfKey } from '@app/utils/layout-containers';
import type { PageBlock } from '@app/utils/layout-containers';
import { actionText } from '@app/utils/theme-contrast';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

type ContainerBlock = Extract<PageBlock<StandardFormFieldDto>, { kind: 'container' }>;

/** How many of these questions have a problem flagged now (a question inside a repeating group counts for the group). */
function useAttention(page: StandardFormFieldDto | undefined, members: StandardFormFieldDto[]): number {
    const { formResponse } = useFormResponse();
    const invalid = Object.keys(formResponse.invalidFields ?? {});
    if (!invalid.length) return 0;
    const own = new Set(members.map((member) => member.id));
    const flagged = new Set<string>();
    for (const key of invalid) {
        const member = memberIdOfKey(page, key);
        if (member && own.has(member)) flagged.add(member);
    }
    return flagged.size;
}

const CARD = 'rounded-xl border bg-white/70 p-4 md:p-6';
/** The same 12-column grid the page lays its questions out on (form-slide.tsx). */
const INNER_GRID = 'flex flex-col gap-12 lg:grid lg:grid-cols-12 lg:gap-x-6 lg:gap-y-12';

/**
 * A layout container (utils/layout-containers.ts) as the respondent sees it:
 * a panel that opens and closes, a bordered field set, or a strip of tabs.
 * Layout only: the questions render, answer and validate exactly as they do
 * outside a container. `renderMembers` draws a list of questions in the
 * page's grid; closed panels and other tabs stay mounted (`hidden`), so what
 * was typed is not lost and the answers stay in the form.
 */
export default function LayoutContainerBlock({ page, block, renderMembers }: { page: StandardFormFieldDto | undefined; block: ContainerBlock; renderMembers: (members: StandardFormFieldDto[]) => ReactNode }) {
    const { container } = block;
    if (container.type === 'tabs') return <TabsBlock page={page} container={container} tabs={block.tabs ?? []} renderMembers={renderMembers} />;
    if (container.type === 'fieldset') return <FieldsetBlock page={page} container={container} members={block.members} renderMembers={renderMembers} />;
    return <PanelBlock page={page} container={container} members={block.members} renderMembers={renderMembers} />;
}

/** A polite status region of its own: what was opened for a problem is said once, here. */
function Notice({ text }: { text?: string }) {
    return (
        <p role="status" className="sr-only">
            {text ?? ''}
        </p>
    );
}

function useBorder() {
    const { theme } = useFormState();
    return { borderColor: (theme?.tertiary ?? '#818CA0') + '55' };
}

function PanelBlock({ page, container, members, renderMembers }: { page: StandardFormFieldDto | undefined; container: LayoutContainer; members: StandardFormFieldDto[]; renderMembers: (members: StandardFormFieldDto[]) => ReactNode }) {
    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const formId = useAppSelector(selectResponderForm)?.formId;
    const view = useContainerView(formId, container.id);
    const setView = useSetContainerView(formId);
    const open = view?.open ?? !container.collapsed;
    const attention = useAttention(page, members);
    // One level under the page's own heading: the form title (h1), or the
    // Leaflet section bar (h2), as a repeating group's items.
    const Heading = styleTokens(theme?.style).key === 'leaflet' ? 'h3' : 'h2';
    const headingId = `layout-${container.id}-heading`;
    const bodyId = `layout-${container.id}-body`;
    return (
        <section aria-labelledby={headingId} data-layout-container={container.id} data-layout-type="panel" className={CARD} style={useBorder()}>
            <Heading id={headingId} className="m-0 text-base font-semibold text-black-900">
                <button
                    type="button"
                    aria-expanded={open}
                    aria-controls={bodyId}
                    onClick={() => setView(container.id, { open: !open })}
                    className="-m-1 flex min-h-11 w-[calc(100%+0.5rem)] items-center justify-between gap-3 rounded-lg p-1 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
                >
                    <span lang={contentLang}>{container.title}</span>
                    <span className="flex shrink-0 items-center gap-2">
                        {attention > 0 && !open && (
                            <span className="rounded-full border px-2 py-0.5 text-xs font-medium" style={{ borderColor: '#B42318', color: '#B42318' }}>
                                {t('LAYOUT.NEED_ATTENTION', { count: attention })}
                            </span>
                        )}
                        <ChevronDown className={cn('h-5 w-5 transition-transform motion-reduce:transition-none', open && 'rotate-180')} style={{ color: actionText(theme) }} aria-hidden="true" />
                    </span>
                </button>
            </Heading>
            <div id={bodyId} hidden={!open} className="pt-6">
                <div className={INNER_GRID}>{renderMembers(members)}</div>
            </div>
            <Notice text={view?.notice} />
        </section>
    );
}

function FieldsetBlock({ container, members, renderMembers }: { page: StandardFormFieldDto | undefined; container: LayoutContainer; members: StandardFormFieldDto[]; renderMembers: (members: StandardFormFieldDto[]) => ReactNode }) {
    const contentLang = useFormContentLanguage();
    const border = useBorder();
    return (
        <fieldset data-layout-container={container.id} data-layout-type="fieldset" className={cn(CARD, 'm-0 min-w-0')} style={border}>
            <legend className="px-2 text-base font-semibold text-black-900" lang={contentLang}>
                {container.title}
            </legend>
            <div className={cn(INNER_GRID, 'pt-4')}>{renderMembers(members)}</div>
        </fieldset>
    );
}

function TabsBlock({
    page,
    container,
    tabs: all,
    renderMembers
}: {
    page: StandardFormFieldDto | undefined;
    container: LayoutContainer;
    tabs: Array<{ tab: LayoutTab; members: StandardFormFieldDto[] }>;
    renderMembers: (members: StandardFormFieldDto[]) => ReactNode;
}) {
    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const formId = useAppSelector(selectResponderForm)?.formId;
    const view = useContainerView(formId, container.id);
    const setView = useSetContainerView(formId);
    // a tab with no question to show (all hidden by logic, or none) is not offered
    const tabs = all.filter((entry) => entry.members.length > 0);
    const shown = tabs.find((entry) => entry.tab.id === view?.tab) ?? tabs[0];
    const refs = useRef<Array<HTMLButtonElement | null>>([]);
    const border = useBorder();
    if (!tabs.length) return null;

    const select = (index: number) => {
        const next = tabs[(index + tabs.length) % tabs.length];
        setView(container.id, { tab: next.tab.id });
        refs.current[(index + tabs.length) % tabs.length]?.focus();
    };
    // Left and Right (swapped for right-to-left text), Home and End move to a tab and show it.
    const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
        const rtl = typeof getComputedStyle === 'function' && getComputedStyle(event.currentTarget).direction === 'rtl';
        const forward = rtl ? 'ArrowLeft' : 'ArrowRight';
        const backward = rtl ? 'ArrowRight' : 'ArrowLeft';
        if (event.key === forward) select(index + 1);
        else if (event.key === backward) select(index - 1);
        else if (event.key === 'Home') select(0);
        else if (event.key === 'End') select(tabs.length - 1);
        else return;
        event.preventDefault();
    };
    return (
        <div data-layout-container={container.id} data-layout-type="tabs">
            <div role="tablist" aria-label={t('LAYOUT.TABS')} className="flex flex-wrap gap-x-1 border-b" style={border}>
                {tabs.map(({ tab, members }, index) => {
                    const selected = tab === shown.tab;
                    return (
                        <TabButton
                            key={tab.id}
                            tab={tab}
                            members={members}
                            page={page}
                            containerId={container.id}
                            selected={selected}
                            lang={contentLang}
                            ink={actionText(theme)}
                            setRef={(el) => (refs.current[index] = el)}
                            onClick={() => setView(container.id, { tab: tab.id })}
                            onKeyDown={(event) => onKeyDown(event, index)}
                        />
                    );
                })}
            </div>
            {tabs.map(({ tab, members }) => (
                <div key={tab.id} role="tabpanel" id={`layout-${container.id}-${tab.id}-panel`} aria-labelledby={`layout-${container.id}-${tab.id}-tab`} hidden={tab !== shown.tab} className="pt-8">
                    <div className={INNER_GRID}>{renderMembers(members)}</div>
                </div>
            ))}
            <Notice text={view?.notice} />
        </div>
    );
}

function TabButton({
    tab,
    members,
    page,
    containerId,
    selected,
    lang,
    ink,
    setRef,
    onClick,
    onKeyDown
}: {
    tab: LayoutTab;
    members: StandardFormFieldDto[];
    page: StandardFormFieldDto | undefined;
    containerId: string;
    selected: boolean;
    lang?: string;
    ink: string;
    setRef: (element: HTMLButtonElement | null) => void;
    onClick: () => void;
    onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
}) {
    const { t } = useRespondentLanguage();
    const attention = useAttention(page, members);
    return (
        <button
            ref={setRef}
            type="button"
            role="tab"
            id={`layout-${containerId}-${tab.id}-tab`}
            aria-selected={selected}
            aria-controls={`layout-${containerId}-${tab.id}-panel`}
            tabIndex={selected ? 0 : -1}
            onClick={onClick}
            onKeyDown={onKeyDown}
            className={cn(
                '-mb-px flex min-h-11 items-center gap-2 border-b-2 px-3 py-2 text-base font-semibold focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-500',
                selected ? 'text-black-900' : 'border-transparent text-black-700'
            )}
            style={selected ? { borderColor: ink } : undefined}
        >
            <span lang={lang}>{tab.title}</span>
            {attention > 0 && !selected && (
                <span className="rounded-full border px-2 py-0.5 text-xs font-medium" style={{ borderColor: '#B42318', color: '#B42318' }}>
                    {t('LAYOUT.NEED_ATTENTION', { count: attention })}
                </span>
            )}
        </button>
    );
}
