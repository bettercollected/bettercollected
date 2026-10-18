'use client';

import React, { memo, useMemo, useState } from 'react';

import { LogicOutlinedIcon } from '@Components/icons/logic-outlined-icon';
import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';
import { useAtomValue, useSetAtom } from 'jotai';
import { Copy, Lock as LockIcon, Plus, Trash } from 'lucide-react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { formFieldsList } from '@app/constants/form-fields';
import { insertCatalogItem } from '@app/constants/insert-field-catalog';
import { jsonEqual } from '@app/lib/form-ops/model';
import { useBuilderFormLogo } from '@app/lib/hooks/use-form-logo';
import { useUndoableDelete } from '@app/lib/hooks/use-undoable-delete';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { useAIProposalHighlights } from '@app/store/jotai/ai-proposal';
import { useDocValue, useField, usePageFieldIds, usePageShell } from '@app/store/jotai/entity-hooks';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { insertTargetAtom } from '@app/store/jotai/insert-target';
import { useNavbarState } from '@app/store/jotai/navbar';
import { fieldHasLogic } from '@app/utils/conditional-logic';
import { locateField } from '@app/utils/form-outline';
import { leafletMarginWidth, leafletSection, pageSectionTitle, questionNumbers } from '@app/utils/leaflet-sections';
import { ownTitleText } from '@app/utils/publish-checks';
import { hasSeveralPages, plainQuestionNumbers } from '@app/utils/question-numbering';
import CanvasInsertMenu from '@app/views/molecules/form-builder/canvas-insert-menu';
import MoveUpDown from '@app/views/molecules/form-builder/move-up-down';
import PlainLanguageHints from '@app/views/molecules/form-builder/plain-language-hints';
import SectionTitleInput from '@app/views/molecules/form-builder/section-title-input';
import { LeafletSectionBar, LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { actionInk, leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';

import { RichTextEditor } from '../../molecules/rich-text-editor';
import { FORM_COLUMN, clampSpan, columnPlacementClass, fieldSpacingClass } from '../layout/form-column';
import SlideLayoutWrapper from '../layout/slide-layout-wrapper';
import FieldDescription, { FieldDescriptionHints } from './fields/field-description';
import renderFieldWrapper from './fields/render-field';

// Human-readable name for the selected field's type, e.g. "Multiple choice".
function fieldTypeLabel(type?: string) {
    const known = insertCatalogItem(type) ?? formFieldsList.find((f) => f.type === type);
    if (known) return known.name;
    return (type ?? 'Field').replaceAll('_', ' ').toLowerCase();
}

// What an open AI proposal does to a question, on the canvas (ai-proposal.ts).
const PROPOSAL_MARK = {
    added: { label: 'AI · new', title: 'The AI proposes adding this question', ring: 'outline-dashed outline-2 outline-offset-4 outline-[#2E7D4F]', chip: 'bg-[#E7F4EC] text-[#1F5E39]' },
    changed: { label: 'AI · changed', title: 'The AI proposes changing this question', ring: 'outline-dashed outline-2 outline-offset-4 outline-[#B25E09]', chip: 'bg-[#FDF3E7] text-[#8A4A08]' }
};

/** What a screen reader announces for a field on the canvas: its type and title. */
export function canvasFieldName(field: StandardFormFieldDto) {
    const title = ownTitleText(field);
    if (field.type === FieldTypes.TEXT) return title ? `Text block: ${title}` : 'Empty text block';
    const type = fieldTypeLabel(field.type);
    return title ? `${type}: ${title}` : `${type}: untitled`;
}

/**
 * A "+" in the gap above a field (or below the last one): adds a field at
 * that position. Shows on hover of the gap and on keyboard focus.
 */
function InsertSlot({ slide, index, edge }: { slide: StandardFormFieldDto; index: number; edge: 'before' | 'after' }) {
    const setInsertTarget = useSetAtom(insertTargetAtom);
    const id = edge === 'after' ? `canvas-end-${slide.id}` : `insert-slot-${slide.id}-${index}`;
    return (
        <div className={cn('group/slot absolute inset-x-0 z-[5] flex h-6 items-center justify-center', edge === 'before' ? '-top-9' : '-bottom-9')}>
            <span aria-hidden="true" className="absolute inset-x-0 top-1/2 h-px bg-[#123FC9] opacity-0 transition-opacity group-hover/slot:opacity-40" />
            <button
                type="button"
                id={id}
                aria-label={edge === 'after' ? 'Add a field at the end of the page' : `Add a field before question ${index + 1}`}
                title="Add a field here"
                className="relative flex h-6 w-6 items-center justify-center rounded-full border border-[#123FC9] bg-white text-[#123FC9] opacity-0 transition-opacity group-hover/slot:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#123FC9]"
                onClick={(event) => {
                    event.stopPropagation();
                    setInsertTarget({ slideId: slide.id, slideIndex: slide.index, fieldIndex: index, anchorId: id, returnFocusId: id });
                }}
            >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
        </div>
    );
}

/** What the canvas shows of a page that depends on its questions (not on one question alone). */
interface CanvasPageView {
    /** The Leaflet section bar's title (full and shortened), when the style is Leaflet. */
    section: { title: string; shortTitle: string } | null;
    /** What the section bar falls back to without a section title of the page's own. */
    fallbackTitle: string;
    /** Leaflet n.m numbers in the margin, by question id. */
    numbers: Record<string, string>;
    /** The form's question numbering in the other styles, by question id. */
    plainNumbers: Record<string, string>;
    /** The page's opening text block (Leaflet), edited on the intro band. */
    openingId: string | null;
    /** Does that block open with a heading (shown on the section bar)? */
    openingStartsWithHeading: boolean;
}

const NO_VIEW: CanvasPageView = { section: null, fallbackTitle: '', numbers: {}, plainNumbers: {}, openingId: null, openingStartsWithHeading: false };

function canvasPageView(page: StandardFormFieldDto | undefined, leaflet: boolean, severalPages: boolean): CanvasPageView {
    if (!page) return NO_VIEW;
    const fields = page.properties?.fields ?? [];
    const pageNumber = (page.index ?? 0) + 1;
    const emptyLabel = `Section ${pageNumber}`;
    const section = leaflet ? leafletSection(fields, emptyLabel, pageSectionTitle(page)) : null;
    const opening = leaflet && fields[0]?.type === FieldTypes.TEXT ? fields[0] : null;
    const openingDoc = opening && typeof opening.title === 'object' ? (opening.title as any) : null;
    return {
        section: section ? { title: section.title, shortTitle: section.shortTitle } : null,
        fallbackTitle: leaflet ? leafletSection(fields, emptyLabel).shortTitle : '',
        numbers: leaflet ? questionNumbers(fields, pageNumber) : {},
        // Other styles: the form's question numbering, as respondents see it.
        plainNumbers: !leaflet && page.properties?.showQuestionNumbers ? plainQuestionNumbers(fields, pageNumber, severalPages) : {},
        openingId: opening?.id ?? null,
        openingStartsWithHeading: openingDoc?.content?.[0]?.type === 'heading'
    };
}

const HEADING_ON_BAR_CLASSES =
    '[&_.ProseMirror]:leading-[1.6] [&_.ProseMirror>*:first-child]:relative [&_.ProseMirror>*:first-child]:py-3.5 [&_.ProseMirror>*:first-child]:pl-[var(--leaflet-margin,34px)] [&_.ProseMirror>*:first-child]:font-(family-name:--leaflet-serif) [&_.ProseMirror>*:first-child]:text-[22px]! [&_.ProseMirror>*:first-child]:leading-[1.25]! [&_.ProseMirror>*:first-child]:font-semibold! [&_.ProseMirror>*:first-child]:text-white [&_.ProseMirror>*:first-child]:[border-image:conic-gradient(var(--leaflet-bar)_0_0)_fill_0//0_100vmax] [&_.ProseMirror>*:first-child]:before:absolute [&_.ProseMirror>*:first-child]:before:top-3.5 [&_.ProseMirror>*:first-child]:before:left-0 [&_.ProseMirror>*:first-child]:before:text-[28px] [&_.ProseMirror>*:first-child]:before:leading-none [&_.ProseMirror>*:first-child]:before:tabular-nums [&_.ProseMirror>*:first-child]:before:content-(--leaflet-numeral) [&_.ProseMirror>*:last-child:not(:first-child)]:mb-4 [&_.ProseMirror>*:nth-child(2)]:mt-4!';

/** The page's opening text block on the Leaflet intro band (one editor, dressed per block). */
const OpeningBlock = memo(function OpeningBlock({
    fieldId,
    field: given,
    slide,
    active,
    headingOnBar,
    bar,
    sectionNumber
}: {
    fieldId: string;
    field?: StandardFormFieldDto;
    slide: StandardFormFieldDto;
    active: boolean;
    headingOnBar: boolean;
    bar?: string;
    sectionNumber: number;
}) {
    const stored = useField(given ? null : fieldId);
    const opening = given ?? stored;
    const setActiveFieldComponent = useSetAtom(activeFieldAtom);
    if (!opening) return null;
    const selectOpening = (event: React.SyntheticEvent) => {
        event.stopPropagation();
        setActiveFieldComponent({ id: opening.id, index: 0 });
    };
    return (
        // Selected by focus like any field; the click keeps the mat from clearing it.
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
        <div
            role="group"
            aria-label={canvasFieldName(opening)}
            tabIndex={-1}
            onClick={selectOpening}
            onFocus={selectOpening}
            className={cn(FORM_COLUMN, columnPlacementClass(slide.properties?.layout), 'relative cursor-text', active && 'outline-2 outline-offset-2 outline-[#123FC9]', headingOnBar && HEADING_ON_BAR_CLASSES)}
            style={
                {
                    '--leaflet-bar': bar,
                    '--leaflet-serif': leafletSerif.style.fontFamily,
                    '--leaflet-numeral': `"${sectionNumber}"`
                } as React.CSSProperties
            }
        >
            <RichTextEditor field={opening} slide={slide} />
        </div>
    );
});

interface CanvasFieldProps {
    fieldId: string;
    /** The question itself when the canvas shows a given page (a preview), else it is read by id. */
    field?: StandardFormFieldDto;
    /** The page around the question (its own settings; see pageShellAtom). */
    slide: StandardFormFieldDto;
    index: number;
    isLast: boolean;
    disabled: boolean;
    isScaledDown: boolean;
    editable: boolean;
    active: boolean;
    /** Slide in from the left when mounted (a field just inserted from the navbar). */
    slideIn: boolean;
    number?: string;
    plainNumber?: string;
    mark?: keyof typeof PROPOSAL_MARK;
    numberInk?: string;
    primary?: string;
    plainLanguage: FieldDescriptionHints;
}

/**
 * One question on the canvas. It subscribes to its own question only, so
 * typing in it re-renders it (and not its page or the other questions).
 */
const CanvasField = memo(function CanvasField({ fieldId, field: given, slide, index, isLast, disabled, isScaledDown, editable, active, slideIn, number, plainNumber, mark: markKind, numberInk, primary, plainLanguage }: CanvasFieldProps) {
    const stored = useField(given ? null : fieldId);
    const field = given ?? stored;
    const setActiveFieldComponent = useSetAtom(activeFieldAtom);
    const { duplicateField, getFormFields } = useBuilderActions();
    const { deleteQuestion } = useUndoableDelete();
    // The toolbar acts on the question where it is now, found by id.
    const locate = () => (field ? locateField(getFormFields(), field.id) : null);
    if (!field) return null;
    // Tips show for the question being edited only, so the canvas stays calm.
    const showHints = !disabled && !isScaledDown && active;
    const titleHintsId = `plain-language-title-${field.id}`;
    const mark = !isScaledDown && markKind ? PROPOSAL_MARK[markKind] : undefined;
    const select = (event: React.SyntheticEvent) => {
        event.preventDefault();
        event.stopPropagation();
        setActiveFieldComponent({ id: field.id, index });
    };
    return (
        <motion.div
            {...({
                initial: { x: slideIn ? '-10%' : 0 },
                animate: { x: 0 },
                transition: { duration: 0.5 },
                id: disabled ? field.id : `scroll-field-${field.id}`,
                // WYSIWYG: the canvas packs columns exactly like the runtime.
                style: { gridColumn: `span ${clampSpan(field)} / span ${clampSpan(field)}` },
                // Rows size to content — h-full made every row stretch to an
                // equal share of the slide, so spacing changed with field count.
                className: cn('relative flex w-full min-w-0 flex-row items-center', fieldSpacingClass(field, isLast))
            } as any)}
        >
            {editable && <InsertSlot slide={slide} index={index} edge="before" />}
            {editable && isLast && <InsertSlot slide={slide} index={index + 1} edge="after" />}
            {/* Selecting goes by focus, for keyboard and pointer alike; the
                click handler only keeps the canvas mat from clearing it. */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions */}
            <div
                key={index}
                role="group"
                aria-label={canvasFieldName(field)}
                // Tab reaches each question, so the keyboard can select it.
                // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
                tabIndex={editable ? 0 : -1}
                data-canvas-field={editable ? field.id : undefined}
                className={cn('w-full cursor-pointer rounded-lg p-1 outline-hidden focus-visible:ring-2 focus-visible:ring-[#123FC9] focus-visible:ring-offset-2', active && 'ring-2 ring-[#123FC9]', mark && mark.ring)}
                onFocus={select}
                onClick={select}
            >
                <div className={'relative flex flex-col items-start'}>
                    {mark && (
                        <div data-testid={`ai-mark-${field.id}`} title={mark.title} className={`absolute -top-6 right-0 z-10 inline-flex items-center rounded px-1.5 py-[2px] text-[10px] font-semibold ${mark.chip}`}>
                            {mark.label}
                        </div>
                    )}
                    {!isScaledDown && field.internal && (
                        <div className="absolute -top-6 left-0 z-10 inline-flex items-center gap-1 rounded bg-black-200 px-1.5 py-[2px] text-[10px] font-semibold text-black-700" title="Respondents never see this field — your team fills it in on each response">
                            <LockIcon className="h-3 w-3" aria-hidden="true" />
                            Internal · staff only
                        </div>
                    )}
                    {!isScaledDown && !field.internal && fieldHasLogic(field) && (
                        <div className="absolute -top-6 left-0 z-10 inline-flex items-center gap-1 rounded bg-brand-100 px-1.5 py-[2px] text-[10px] font-semibold text-brand-500" title="This field is shown/hidden by a logic rule">
                            <LogicOutlinedIcon className="h-3 w-3" aria-hidden="true" />
                            Logic
                        </div>
                    )}
                    {!isScaledDown && active && (
                        // Selection toolbar: what this field is, then what you can do
                        // with it. Delete is last and quiet-red — a destructive action
                        // shouldn't be the selection's only (or loudest) affordance.
                        <div role="toolbar" aria-label="Question actions" className="absolute -top-12 right-0 z-20 flex items-center overflow-hidden rounded border border-black-300 bg-white shadow-large">
                            <span className="px-2.5 text-[11px] font-semibold tracking-wide text-black-600 uppercase">{fieldTypeLabel(field.type)}</span>
                            <span className="h-5 w-px bg-black-400" aria-hidden="true" />
                            <button
                                type="button"
                                aria-label="Duplicate question"
                                aria-keyshortcuts="Control+D Meta+D"
                                title="Duplicate question (Ctrl/Cmd+D)"
                                className="p-2 text-black-700 hover:bg-black-100 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#123FC9]"
                                onClick={(event) => {
                                    event.stopPropagation();
                                    const at = locate();
                                    if (at) duplicateField(at.pageIndex, at.fieldIndex);
                                }}
                            >
                                <Copy width={16} height={16} aria-hidden="true" />
                            </button>
                            <button
                                type="button"
                                aria-label="Delete question"
                                aria-keyshortcuts="Delete"
                                title="Delete question (Delete)"
                                className="p-2 text-[#C43D3D] hover:bg-[#FBEFEF] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#123FC9]"
                                onClick={(event) => {
                                    event.stopPropagation();
                                    const at = locate();
                                    if (at) deleteQuestion(at.pageIndex, at.fieldIndex);
                                }}
                            >
                                <Trash width={16} height={16} aria-hidden="true" />
                            </button>
                        </div>
                    )}
                    {active && (
                        <div className={cn('absolute -left-10 -mt-1 text-black-600', '', isScaledDown ? 'hidden' : '')}>
                            <MoveUpDown fieldId={field.id} />
                        </div>
                    )}
                    <div className={cn('mb-2 w-full', number && '[&>*:not(:first-child)]:pl-[var(--leaflet-margin,34px)]')}>
                        <div className={cn('relative w-full', number ? 'grid grid-cols-[var(--leaflet-margin,34px)_minmax(0,1fr)] items-baseline' : 'flex items-center gap-2')}>
                            {number && (
                                <span aria-hidden="true" className="text-[16px] leading-[1.4] tabular-nums" style={{ fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: numberInk }}>
                                    {number}
                                </span>
                            )}
                            {plainNumber && (
                                <span aria-hidden="true" data-testid="canvas-question-number" className="shrink-0 self-start text-2xl font-semibold tabular-nums" style={{ color: primary }}>
                                    {plainNumber}
                                </span>
                            )}
                            {/* A question's title in the theme's title face, as respondents see it (theme-root.ts). */}
                            <div className={cn('contents', field.type !== FieldTypes.TEXT && 'form-title-face')}>
                                <RichTextEditor field={field} slide={slide} isRequired={field?.validations?.required} describedById={titleHintsId} />
                            </div>
                        </div>
                        {showHints && <PlainLanguageHints id={titleHintsId} value={field.title} {...plainLanguage} />}
                        <FieldDescription field={field} disabled={disabled} hints={showHints ? plainLanguage : undefined} />
                    </div>
                    <div className={cn('w-full', number && 'pl-[var(--leaflet-margin,34px)]')}>{renderFieldWrapper(field, slide, disabled)}</div>
                </div>
            </div>
        </motion.div>
    );
});

interface SlideBuilderProps {
    /** The page to edit, read from the form document by id (the builder's canvas). */
    pageId?: string;
    /** A page to show as given instead (the AI proposal preview, tests). */
    slide?: StandardFormFieldDto;
    isScaledDown?: boolean;
    disabled?: boolean;
    /** The proposal preview shows its own theme. */
    themeOverride?: any;
}

/**
 * A page on the canvas. With `pageId` it subscribes to the page's own
 * settings and the order of its questions only; each question subscribes
 * to itself (CanvasField), so typing in one question re-renders that
 * question alone. With `slide` it shows that page as given.
 */
const SlideBuilder = ({ pageId, slide: given, isScaledDown = false, disabled = false, themeOverride }: SlideBuilderProps) => {
    const live = !given;
    const shell = usePageShell(live ? pageId : null);
    const storedIds = usePageFieldIds(live ? pageId : null);
    const slide = given ?? shell;
    const givenFields = given?.properties?.fields;
    const fieldIds = useMemo(() => (live ? storedIds : (givenFields ?? []).map((field) => field.id)), [live, storedIds, givenFields]);
    const givenById = useMemo(() => new Map((givenFields ?? []).map((field) => [field.id, field])), [givenFields]);

    const { updateSlideSectionTitle } = useBuilderActions();
    const activeFieldComponent = useAtomValue(activeFieldAtom);
    const activeSlideComponent = useAtomValue(activeSlideAtom);
    const { theme: editorTheme } = useFormState();
    const theme = themeOverride ?? editorTheme;
    const proposalMarks = useAIProposalHighlights().fields;
    const logo = useBuilderFormLogo();
    const { navbarState } = useNavbarState();
    const setInsertTarget = useSetAtom(insertTargetAtom);
    // The page being edited (not a preview): insert slots, shortcuts, focus.
    const editable = !disabled && !isScaledDown;
    // Plain-language tips use the form's declared language when it has one.
    const form = useAppSelector(selectForm);
    const formId = form?.formId;
    const formLanguage = form?.settings?.language;
    const plainLanguage = useMemo(() => ({ formId, formLanguage }), [formId, formLanguage]);
    // Leaflet (WYSIWYG with the respondent page): the numbered section bar,
    // the opening text block on the intro band, n.m numbers in the margin.
    // The canvas shows every field, so numbering follows the page's order.
    const leaflet = styleTokens(theme?.style).key === 'leaflet';
    const severalPages = useDocValue((doc) => hasSeveralPages(doc.fields), []);
    // What depends on the page's questions together: recomputed as they
    // change, re-rendering the page only when the result changes.
    const liveView = useDocValue((doc) => (live && pageId ? canvasPageView(doc.fields?.find((page) => page?.id === pageId), leaflet, hasSeveralPages(doc.fields)) : NO_VIEW), [live, pageId, leaflet], jsonEqual);
    const view = live ? liveView : canvasPageView(given, leaflet, severalPages);
    const [editingBarTitle, setEditingBarTitle] = useState(false);
    if (!slide) return null;

    // The page's own section title wins; without one the bar falls back to
    // the opening heading, then the first question (utils/leaflet-sections.ts).
    const ownTitle = pageSectionTitle(slide);
    const { section, fallbackTitle, numbers, plainNumbers } = view;
    const numberInk = actionInk(theme);
    // The page's opening text block is edited where respondents see it: its
    // heading as the title on the navy section bar, the rest on the intro
    // band (one editor, dressed per block), instead of a second copy below.
    // With a section title of its own (or while one is being typed) the bar
    // edits that title and the heading stays in the band.
    const openingId = view.openingId;
    const headingOnBar = !ownTitle && !editingBarTitle && view.openingStartsWithHeading;
    const barTitleEditor =
        !disabled && !isScaledDown && slide?.index !== undefined ? (
            <SectionTitleInput value={slide.properties?.sectionTitle ?? ''} placeholder={fallbackTitle} onChange={(value) => updateSlideSectionTitle(slide.index, value)} onFocusChange={setEditingBarTitle} />
        ) : undefined;
    const sectionNumber = (slide?.index ?? 0) + 1;
    const marginVar = leaflet ? ({ ['--leaflet-margin' as string]: `${leafletMarginWidth(numbers, sectionNumber)}px` } as React.CSSProperties) : undefined;
    const slideIn = !!navbarState.insertClicked && activeSlideComponent?.id === slide.id;

    return (
        <SlideLayoutWrapper showDesktopLayout slide={slide} disabled={disabled} theme={theme} scrollDivId={!disabled ? 'scroll-div' : undefined} topAligned={leaflet} logo={logo}>
            {leaflet && section && (
                <div style={marginVar}>
                    <LeafletTopRule theme={theme} />
                    {!headingOnBar && <LeafletSectionBar theme={theme} numeral={sectionNumber} title={section.shortTitle} fullTitle={section.title} layout={slide.properties?.layout} titleEditor={barTitleEditor} />}
                    {openingId && (
                        <div
                            // Full width like the respondent's bar and band; the
                            // heading's navy reaches the page edges through a
                            // filled border image (no box, no shadow), clipped here.
                            className={cn('-mx-5 overflow-x-clip px-5 sm:-mx-8 sm:px-8', !headingOnBar && 'py-4')}
                            style={{ background: leafletColours(theme).band, color: theme?.primary }}
                            data-testid="leaflet-canvas-opening"
                        >
                            <OpeningBlock fieldId={openingId} field={givenById.get(openingId)} slide={slide} active={activeFieldComponent?.id === openingId} headingOnBar={headingOnBar} bar={theme?.secondary} sectionNumber={sectionNumber} />
                        </div>
                    )}
                </div>
            )}
            {/* WYSIWYG: the same form column, 48px question rhythm and
                vertical placement as the respondent page (form-column.ts);
                pt-12 matches the space the respondent page keeps for its
                header bar. */}
            <div
                className={cn('w-full outline-hidden', leaflet ? 'pt-7' : 'pt-12')}
                style={marginVar}
                // Keyboard shortcuts act while focus is on the canvas (use-builder-shortcuts).
                {...(editable ? { 'data-builder-canvas': true, tabIndex: -1 } : {})}
            >
                <div
                    className={cn(
                        FORM_COLUMN,
                        // Page alignment positions the column, not each field.
                        columnPlacementClass(slide.properties?.layout),
                        // The respondent's desktop grid (lg: from a 1024px window,
                        // where a page is at least 448px wide). The canvas is a
                        // fixed desktop-size page at any window width, so it asks
                        // its page container (LayoutWrapper's @container/page),
                        // not the window.
                        'flex flex-col gap-12 @min-[448px]/page:grid @min-[448px]/page:grid-cols-12 @min-[448px]/page:gap-x-6 @min-[448px]/page:gap-y-12'
                    )}
                >
                    <AnimatePresence>
                        {fieldIds.length ? (
                            fieldIds.map((fieldId, index) =>
                                openingId && fieldId === openingId ? null : (
                                    <CanvasField
                                        key={fieldId}
                                        fieldId={fieldId}
                                        field={givenById.get(fieldId)}
                                        slide={slide}
                                        index={index}
                                        isLast={index === fieldIds.length - 1}
                                        disabled={disabled}
                                        isScaledDown={isScaledDown}
                                        editable={editable}
                                        active={activeFieldComponent?.id === fieldId}
                                        slideIn={slideIn}
                                        number={numbers[fieldId]}
                                        plainNumber={plainNumbers[fieldId]}
                                        mark={proposalMarks[fieldId] as keyof typeof PROPOSAL_MARK | undefined}
                                        numberInk={numberInk}
                                        primary={theme?.primary}
                                        plainLanguage={plainLanguage}
                                    />
                                )
                            )
                        ) : !disabled && !isScaledDown ? (
                            // An empty page shouldn't be a dead rectangle — give
                            // first-run creators a direct way in (audit B4).
                            <div className="flex h-full w-full items-center justify-center @min-[448px]/page:col-span-12">
                                <button
                                    type="button"
                                    id={`canvas-end-${slide.id}`}
                                    aria-keyshortcuts="/"
                                    className="flex flex-col items-center gap-2 rounded border border-dashed border-black-400 bg-white/60 px-10 py-8 text-sm font-medium text-black-700 transition-colors hover:border-black-600 hover:text-black-900"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        setInsertTarget({ slideId: slide.id, slideIndex: slide.index, fieldIndex: 0, anchorId: `canvas-end-${slide.id}`, returnFocusId: `canvas-end-${slide.id}` });
                                    }}
                                >
                                    <span className="text-2xl leading-none" aria-hidden="true">
                                        ＋
                                    </span>
                                    Add a question
                                    <span className="text-xs font-normal text-black-600">Pick a field type, or press / on the page</span>
                                </button>
                            </div>
                        ) : (
                            <></>
                        )}
                    </AnimatePresence>
                </div>
            </div>
            {editable && <CanvasInsertMenu slide={slide} />}
        </SlideLayoutWrapper>
    );
};
export default SlideBuilder;
