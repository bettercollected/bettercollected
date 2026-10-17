'use client';

import { ReactNode, useEffect, useMemo, useState } from 'react';

import { Announcements, closestCenter, DndContext, DragEndEvent, DragOverlay, DragStartEvent, KeyboardSensor, MeasuringStrategy, Modifier, PointerSensor, UniqueIdentifier, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { AlertTriangle, ChevronRight, GripVertical, Lock, Search } from 'lucide-react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { ActiveFormBuilderComponent, useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import { useAIProposalHighlights } from '@app/store/jotai/ai-proposal';
import { useFormState } from '@app/store/jotai/form';
import { fieldHasLogic } from '@app/utils/conditional-logic';
import { isPageKey, keyId, locateField, outlinePageName, pageKey, pageStatus, PageStatus, questionDropTarget, questionKey, questionMatches, resolveOutlineDrop } from '@app/utils/form-outline';
import { asksForIdentity } from '@app/utils/publish-checks';
import { fieldText } from '@app/views/molecules/form-builder/condition-editor-shared';
import { LogicOutlinedIcon } from '@Components/icons/logic-outlined-icon';

import AddSlidePopover from './add-slide/add-slide-popover';
import QuestionOptions from './outline/question-options';
import { MoveOutcome, useOutlineMoves } from './outline/use-outline-moves';
import SlideOptions from './slide-options';

/**
 * The builder's outline: Welcome, then each page with its questions, then
 * the endings. Pages and questions reorder by drag (pointer or keyboard,
 * with spoken announcements) or from their "…" menu; every move is one undo
 * step. A list of buttons, so every row works with Tab and Enter.
 */

const SR_INSTRUCTIONS =
    'To reorder, press Space or Enter on the move handle, use the up and down arrow keys to move, then Space or Enter to drop, or Escape to cancel. The options menu next to each item also has Move up and Move down.';

// The outline only reorders: drags stay on the vertical axis.
const verticalOnly: Modifier = ({ transform }) => ({ ...transform, x: 0 });

const rowClass = (selected: boolean) => cn('group/row relative flex items-start gap-0.5 rounded px-1 py-1', selected ? 'bg-brand-100' : 'hover:bg-black-200');
const selectButtonClass = 'flex min-w-0 flex-1 flex-col items-start gap-0.5 rounded-sm px-1 py-0.5 text-left';
const handleClass = 'text-black-600 hover:text-black-900 flex h-6 w-5 shrink-0 cursor-grab touch-none items-center justify-center rounded-sm opacity-0 transition-opacity focus-visible:opacity-100 group-hover/row:opacity-100 pointer-coarse:opacity-100';

function Chip({ tone, title, children }: { tone: 'logic' | 'danger' | 'warning' | 'neutral' | 'ai'; title?: string; children: ReactNode }) {
    const tones = {
        ai: 'bg-[#FDF3E7] text-[#8A4A08]',
        logic: 'bg-brand-100 text-brand-600',
        danger: 'bg-[#FBEFEF] text-[#C43D3D]',
        warning: 'bg-brand-accent-100 text-brand-olive',
        neutral: 'bg-black-200 text-black-700'
    };
    return (
        <span title={title} className={cn('inline-flex items-center gap-0.5 rounded px-1 py-[1px] text-[11px] font-medium leading-4', tones[tone])}>
            {children}
        </span>
    );
}

/** ``aiChanges``: changes an open AI proposal makes on this page. */
function PageChips({ status, aiChanges = 0 }: { status: PageStatus; aiChanges?: number }) {
    const chips: ReactNode[] = [];
    if (aiChanges > 0)
        chips.push(
            <Chip key="ai" tone="ai" title={`The AI proposes ${aiChanges} change${aiChanges === 1 ? '' : 's'} on this page`}>
                <span aria-hidden="true">AI · {aiChanges}</span>
                <span className="sr-only">
                    {aiChanges} proposed AI change{aiChanges === 1 ? '' : 's'}
                </span>
            </Chip>
        );
    if (status.brokenJumps > 0)
        chips.push(
            <Chip key="broken" tone="danger" title="A page jump points at a page that no longer exists">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                Broken jump
            </Chip>
        );
    if (status.empty)
        chips.push(
            <Chip key="empty" tone="warning" title="Respondents will see a blank page: add a question or delete it">
                Empty
            </Chip>
        );
    if (status.missingWhyWeAsk > 0)
        chips.push(
            <Chip key="why" tone="warning" title={`${status.missingWhyWeAsk} question${status.missingWhyWeAsk === 1 ? ' asks' : 's ask'} for personal details without a "Why we ask this" line`}>
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                <span aria-hidden="true">Why we ask</span>
                <span className="sr-only">Missing why we ask</span>
            </Chip>
        );
    if (status.hasLogic)
        chips.push(
            <Chip key="logic" tone="logic" title="This page has logic">
                <LogicOutlinedIcon className="h-2.5 w-2.5" aria-hidden="true" />
                Logic
            </Chip>
        );
    if (status.internal > 0)
        chips.push(
            <Chip key="internal" tone="neutral" title="Respondents never see internal questions; your team fills them in">
                <Lock className="h-2.5 w-2.5" aria-hidden="true" />
                {status.internal} internal
            </Chip>
        );
    return chips.length ? <span className="flex flex-wrap gap-1 pt-0.5">{chips}</span> : null;
}

/** A row the outline can drag: `children` gets the move handle to render. */
function SortableRow({ id, label, disabled, selected, className, children }: { id: string; label: string; disabled: boolean; selected: boolean; className?: string; children: (handle: ReactNode) => ReactNode }) {
    const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id, disabled });
    const handle = disabled ? (
        <span className="w-5 shrink-0" aria-hidden="true" />
    ) : (
        <button type="button" ref={setActivatorNodeRef} {...attributes} {...listeners} aria-label={`Move ${label}`} className={cn(handleClass, selected && 'opacity-100')}>
            <GripVertical className="h-4 w-4" aria-hidden="true" />
        </button>
    );
    return (
        <div ref={setNodeRef} data-outline-row="" style={{ transform: CSS.Translate.toString(transform), transition }} className={cn(rowClass(selected), isDragging && 'opacity-40', className)}>
            {children(handle)}
        </div>
    );
}

/** A non-draggable row (Welcome, endings). */
function StaticRow({ label, secondary, selected, onSelect, chip }: { label: string; secondary?: string; selected: boolean; onSelect: () => void; chip?: ReactNode }) {
    return (
        <div className={rowClass(selected)}>
            <span className="w-5 shrink-0" aria-hidden="true" />
            <button type="button" className={selectButtonClass} aria-current={selected ? 'true' : undefined} onClick={onSelect}>
                <span className="text-black-900 text-sm font-medium">{label}</span>
                {secondary ? <span className="text-black-600 line-clamp-1 text-xs">{secondary}</span> : null}
                {chip}
            </button>
        </div>
    );
}

interface ShownPage {
    slide: StandardFormFieldDto;
    index: number;
    name: string;
    expanded: boolean;
    questions: Array<{ field: StandardFormFieldDto; index: number; title: string }>;
}

function LeftDrawer({ formFields, activeSlideComponent }: { formFields: Array<StandardFormFieldDto>; activeSlideComponent: ActiveFormBuilderComponent | null }) {
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { activeThankYouPageComponent, setActiveThankYouPageComponent } = useActiveThankYouPageComponent();
    const { formState } = useFormState();
    const { movePageTo, moveQuestion } = useOutlineMoves();
    const proposed = useAIProposalHighlights();

    const [query, setQuery] = useState('');
    const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
    const [dragging, setDragging] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [focusKey, setFocusKey] = useState<string | null>(null);

    const slides = useMemo(() => (Array.isArray(formFields) ? formFields : []), [formFields]);
    const filtering = query.trim().length > 0;
    const draggingPage = !!dragging && isPageKey(dragging);
    const slideIds = useMemo(() => new Set(slides.map((slide) => slide.id)), [slides]);

    const pages: ShownPage[] = useMemo(
        () =>
            slides
                .map((slide, index) => ({
                    slide,
                    index,
                    name: outlinePageName(slide, index),
                    expanded: filtering || !collapsed.has(slide.id),
                    questions: (slide.properties?.fields ?? []).map((field, fieldIndex) => ({ field, index: fieldIndex, title: fieldText(field) })).filter(({ field }) => questionMatches(field, query))
                }))
                .filter((page) => !filtering || page.questions.length > 0),
        [slides, collapsed, filtering, query]
    );
    const matchCount = pages.reduce((sum, page) => sum + page.questions.length, 0);

    // One flat sortable list: each page followed by its shown questions.
    // While a page is dragged its questions fold away, so pages move as blocks.
    const flatKeys = useMemo(() => pages.flatMap((page) => [pageKey(page.slide.id), ...(page.expanded && !draggingPage ? page.questions.map((q) => questionKey(q.field.id)) : [])]), [pages, draggingPage]);

    const nameOf = (key: UniqueIdentifier): string => {
        const id = keyId(String(key));
        if (isPageKey(String(key))) {
            const index = slides.findIndex((slide) => slide.id === id);
            return outlinePageName(slides[index], index);
        }
        const at = locateField(slides, id);
        return at ? `question ${fieldText(slides[at.pageIndex].properties!.fields![at.fieldIndex])}` : 'item';
    };

    /** Where dropping `active` on `over` would put it, in words. */
    const describeDrop = (active: UniqueIdentifier, over: UniqueIdentifier | undefined): string | null => {
        if (over === undefined) return null;
        const drop = resolveOutlineDrop(flatKeys, String(active), String(over));
        if (!drop) return null;
        if (drop.kind === 'page') return `position ${drop.to + 1} of ${slides.length}`;
        const target = questionDropTarget(slides, drop.fieldId, drop.toPageId, drop.afterFieldId);
        if (!target) return null;
        return `${outlinePageName(slides[target.toPageIndex], target.toPageIndex)}, position ${target.toIndex + 1}`;
    };

    const announcements: Announcements = {
        onDragStart: ({ active }) => `Picked up ${nameOf(active.id)}.`,
        onDragOver: ({ active, over }) => {
            const where = describeDrop(active.id, over?.id);
            return where ? `${nameOf(active.id)} would move to ${where}.` : `${nameOf(active.id)} stays where it was.`;
        },
        onDragEnd: ({ active, over }) => {
            const where = describeDrop(active.id, over?.id);
            return where ? `Dropped ${nameOf(active.id)} at ${where}.` : `Dropped ${nameOf(active.id)} where it was.`;
        },
        onDragCancel: ({ active }) => `Moving ${nameOf(active.id)} was cancelled.`
    };

    const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));

    const onDragStart = ({ active }: DragStartEvent) => setDragging(String(active.id));
    const onDragEnd = ({ active, over }: DragEndEvent) => {
        setDragging(null);
        if (!over) return;
        const drop = resolveOutlineDrop(flatKeys, String(active.id), String(over.id));
        if (!drop) return;
        if (drop.kind === 'page') {
            movePageTo(drop.from, drop.to);
            return;
        }
        const target = questionDropTarget(slides, drop.fieldId, drop.toPageId, drop.afterFieldId);
        if (target) moveQuestion(drop.fieldId, target.toPageIndex, target.toIndex);
    };

    // A menu move: say where the item went and keep focus on it.
    const onMenuMoved = (key: string) => (outcome: MoveOutcome) => {
        if (!outcome) return;
        setMessage(outcome.message);
        // A question moved into a folded page: unfold it, so focus can follow.
        setCollapsed((prev) => (prev.has(outcome.pageId) ? new Set([...prev].filter((id) => id !== outcome.pageId)) : prev));
        setFocusKey(key);
    };
    useEffect(() => {
        if (!focusKey) return;
        // After the menu has closed and let go of focus.
        const timer = window.setTimeout(() => {
            document.querySelector<HTMLElement>(`[data-outline-key="${cssEscape(focusKey)}"]`)?.focus();
            setFocusKey(null);
        }, 0);
        return () => window.clearTimeout(timer);
    }, [focusKey]);

    // Selecting on the canvas brings the row into view.
    useEffect(() => {
        const key = activeFieldComponent?.id ? questionKey(activeFieldComponent.id) : activeSlideComponent && activeSlideComponent.index >= 0 ? pageKey(activeSlideComponent.id) : null;
        if (key) document.querySelector(`[data-outline-key="${cssEscape(key)}"]`)?.scrollIntoView?.({ block: 'nearest' });
    }, [activeFieldComponent?.id, activeSlideComponent]);

    const selectPage = (slide: StandardFormFieldDto, index: number) => {
        setActiveSlideComponent({ id: slide.id, index });
        setActiveFieldComponent(null);
    };
    // As clicking the question on the canvas does: its page, then the question.
    const selectQuestion = (slide: StandardFormFieldDto, index: number, field: StandardFormFieldDto, fieldIndex: number) => {
        setActiveSlideComponent({ id: slide.id, index });
        setActiveFieldComponent({ id: field.id, index: fieldIndex });
        window.setTimeout(() => document.getElementById(`scroll-field-${field.id}`)?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' }), 50);
    };
    const toggle = (pageId: string) =>
        setCollapsed((prev) => {
            const next = new Set(prev);
            if (next.has(pageId)) next.delete(pageId);
            else next.add(pageId);
            return next;
        });

    const endings = formState.thankyouPage?.length ? formState.thankyouPage : [{}];
    const activeEnding = activeThankYouPageComponent?.index ?? 0;
    const isActiveSlide = (id: string) => activeSlideComponent?.id === id;

    return (
        <aside id="slides-preview" aria-label="Form outline" className="h-body-content border-r-black-300 flex w-[256px] shrink-0 flex-col overflow-hidden border-r bg-white">
            <div className="flex w-full items-center justify-between px-4 pb-2 pt-4">
                <h2 className="text-black-900 text-sm font-semibold">Outline</h2>
                <AddSlidePopover />
            </div>
            <div className="relative px-3 pb-3">
                <Search className="text-black-600 pointer-events-none absolute left-5 top-2 h-4 w-4" aria-hidden="true" />
                <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    aria-label="Filter questions by title"
                    placeholder="Filter questions"
                    className="border-control text-black-900 placeholder:text-black-600 focus:border-brand-500 w-full rounded border bg-white py-1.5 pl-8 pr-2 text-sm"
                />
            </div>
            <div id="outline-announcer" className="sr-only" aria-live="polite" role="status">
                {filtering ? `${matchCount} question${matchCount === 1 ? '' : 's'} match.` : message}
            </div>

            <div className="border-t-black-300 flex-1 overflow-y-auto overflow-x-hidden border-t px-2 py-2">
                {!filtering && (
                    <StaticRow
                        label="Welcome"
                        secondary={formState.welcomePage?.title || formState.title || undefined}
                        selected={isActiveSlide('welcome-page')}
                        onSelect={() => {
                            setActiveSlideComponent({ id: 'welcome-page', index: -10 });
                            setActiveFieldComponent(null);
                        }}
                    />
                )}

                {filtering && pages.length === 0 && <p className="text-black-600 px-2 py-3 text-sm">No questions match “{query.trim()}”.</p>}

                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    modifiers={[verticalOnly]}
                    measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}
                    accessibility={{ announcements, screenReaderInstructions: { draggable: SR_INSTRUCTIONS } }}
                    onDragStart={onDragStart}
                    onDragEnd={onDragEnd}
                    onDragCancel={() => setDragging(null)}
                >
                    <SortableContext items={flatKeys} strategy={verticalListSortingStrategy}>
                        <ul aria-label="Pages" className="flex flex-col gap-0.5 py-1">
                            {pages.map((page) => {
                                const { slide, index, name } = page;
                                const key = pageKey(slide.id);
                                const selected = isActiveSlide(slide.id) && !activeFieldComponent?.id;
                                const count = slide.properties?.fields?.length ?? 0;
                                const listId = `outline-questions-${slide.id}`;
                                const showQuestions = page.expanded && !draggingPage && page.questions.length > 0;
                                return (
                                    <li key={slide.id} id={slide.id}>
                                        <SortableRow id={key} label={name} disabled={filtering} selected={selected}>
                                            {(handle) => (
                                                <>
                                                    {handle}
                                                    {count > 0 && !filtering ? (
                                                        <button
                                                            type="button"
                                                            aria-expanded={page.expanded}
                                                            aria-controls={page.expanded ? listId : undefined}
                                                            aria-label={`Questions on ${name}`}
                                                            onClick={() => toggle(slide.id)}
                                                            className="text-black-600 hover:text-black-900 flex h-6 w-5 shrink-0 items-center justify-center rounded-sm"
                                                        >
                                                            <ChevronRight className={cn('h-4 w-4 transition-transform', page.expanded && 'rotate-90')} aria-hidden="true" />
                                                        </button>
                                                    ) : (
                                                        <span className="w-5 shrink-0" aria-hidden="true" />
                                                    )}
                                                    <button type="button" data-outline-key={key} className={selectButtonClass} aria-current={selected ? 'true' : undefined} onClick={() => selectPage(slide, index)}>
                                                        <span className="text-black-900 line-clamp-2 text-sm font-medium">{name}</span>
                                                        <span className="text-black-600 text-xs">
                                                            {slide.properties?.sectionTitle?.trim() ? `Page ${index + 1} · ` : ''}
                                                            {count} question{count === 1 ? '' : 's'}
                                                        </span>
                                                        <PageChips status={pageStatus(slide, slideIds)} aiChanges={proposed.pages[slide.id] ?? 0} />
                                                    </button>
                                                    <SlideOptions slideIndex={index} pageName={name} visible={selected} onMoved={onMenuMoved(key)} />
                                                </>
                                            )}
                                        </SortableRow>
                                        {showQuestions && (
                                            <ul id={listId} aria-label={`Questions on ${name}`} className="flex flex-col gap-0.5 pl-4">
                                                {page.questions.map(({ field, index: fieldIndex, title }) => {
                                                    const qKey = questionKey(field.id);
                                                    const qSelected = activeFieldComponent?.id === field.id;
                                                    const missingWhy = !field.internal && asksForIdentity(field) && !field.properties?.whyWeAsk?.trim();
                                                    return (
                                                        <li key={field.id}>
                                                            <SortableRow id={qKey} label={`question ${title}`} disabled={filtering} selected={qSelected}>
                                                                {(handle) => (
                                                                    <>
                                                                        {handle}
                                                                        <button type="button" data-outline-key={qKey} className={cn(selectButtonClass, 'flex-row items-center gap-1')} aria-current={qSelected ? 'true' : undefined} onClick={() => selectQuestion(slide, index, field, fieldIndex)}>
                                                                            <span className="text-black-800 min-w-0 flex-1 truncate text-sm">{title}</span>
                                                                            {proposed.fields[field.id] && (
                                                                                <span title={proposed.fields[field.id] === 'added' ? 'The AI proposes adding this question' : 'The AI proposes changing this question'} className="shrink-0 rounded bg-[#FDF3E7] px-1 text-[10px] font-semibold leading-4 text-[#8A4A08]">
                                                                                    <span aria-hidden="true">AI</span>
                                                                                    <span className="sr-only">, {proposed.fields[field.id] === 'added' ? 'added' : 'changed'} by an AI proposal</span>
                                                                                </span>
                                                                            )}
                                                                            {missingWhy && (
                                                                                <span title='Asks for personal details without a "Why we ask this" line' className="text-brand-olive shrink-0">
                                                                                    <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                                                                                    <span className="sr-only">, missing why we ask</span>
                                                                                </span>
                                                                            )}
                                                                            {fieldHasLogic(field) && (
                                                                                <span title="Shown or hidden by a logic rule" className="text-brand-500 shrink-0">
                                                                                    <LogicOutlinedIcon className="h-3 w-3" aria-hidden="true" />
                                                                                    <span className="sr-only">, has logic</span>
                                                                                </span>
                                                                            )}
                                                                            {field.internal && (
                                                                                <span title="Internal: respondents never see it" className="text-black-600 shrink-0">
                                                                                    <Lock className="h-3 w-3" aria-hidden="true" />
                                                                                    <span className="sr-only">, internal</span>
                                                                                </span>
                                                                            )}
                                                                        </button>
                                                                        <QuestionOptions fieldId={field.id} title={title} pageIndex={index} fieldIndex={fieldIndex} visible={qSelected} onMoved={onMenuMoved(qKey)} />
                                                                    </>
                                                                )}
                                                            </SortableRow>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                        )}
                                    </li>
                                );
                            })}
                        </ul>
                    </SortableContext>
                    <DragOverlay modifiers={[verticalOnly]} dropAnimation={null}>
                        {dragging ? <div className="border-brand-500 text-black-900 shadow-large truncate rounded border bg-white px-3 py-1.5 text-sm font-medium">{capitalise(nameOf(dragging))}</div> : null}
                    </DragOverlay>
                </DndContext>

                {!filtering && (
                    <div className="border-t-black-300 mt-1 border-t pt-2">
                        <h3 className="text-black-600 px-2 pb-1 text-xs font-medium">{endings.length > 1 ? 'Endings' : 'Ending'}</h3>
                        <ul aria-label="Endings" className="flex flex-col gap-0.5">
                            {endings.map((ending, index) => (
                                <li key={index}>
                                    <StaticRow
                                        label={endings.length > 1 ? `Ending ${index + 1}` : 'Thank you'}
                                        secondary={(ending as any)?.title || (ending as any)?.message || undefined}
                                        selected={isActiveSlide('thank-you-page') && activeEnding === index}
                                        onSelect={() => {
                                            setActiveThankYouPageComponent({ id: `ending-${index}`, index });
                                            setActiveSlideComponent({ id: 'thank-you-page', index: -20 });
                                            setActiveFieldComponent(null);
                                        }}
                                        chip={
                                            index > 0 ? (
                                                <Chip tone="neutral" title="Respondents see the first ending. Choosing an ending by answer is not available yet.">
                                                    Not shown to respondents
                                                </Chip>
                                            ) : undefined
                                        }
                                    />
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </aside>
    );
}

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
// Keys are uuids with a prefix; escape anyway before using one in a selector.
const cssEscape = (value: string) => (typeof window !== 'undefined' && window.CSS?.escape ? window.CSS.escape(value) : value.replace(/["\\]/g, '\\$&'));

export default LeftDrawer;
