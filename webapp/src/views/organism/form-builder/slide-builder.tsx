'use client';

import { useState } from 'react';

import { LogicOutlinedIcon } from '@Components/icons/logic-outlined-icon';
import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';
import { Copy, Lock as LockIcon, Trash } from 'lucide-react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { formFieldsList } from '@app/constants/form-fields';
import { useBuilderFormLogo } from '@app/lib/hooks/use-form-logo';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import { fieldHasLogic } from '@app/utils/conditional-logic';
import { leafletMarginWidth, leafletSection, pageSectionTitle, questionNumbers } from '@app/utils/leaflet-sections';
import MoveUpDown from '@app/views/molecules/form-builder/move-up-down';
import PlainLanguageHints from '@app/views/molecules/form-builder/plain-language-hints';
import SectionTitleInput from '@app/views/molecules/form-builder/section-title-input';
import { LeafletSectionBar, LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { actionInk, leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';

import { RichTextEditor } from '../../molecules/rich-text-editor';
import { FORM_COLUMN, clampSpan, columnPlacementClass, fieldSpacingClass } from '../layout/form-column';
import SlideLayoutWrapper from '../layout/slide-layout-wrapper';
import FieldDescription from './fields/field-description';
import renderFieldWrapper from './fields/render-field';

// Human-readable name for the selected field's type, e.g. "Multiple Choice".
function fieldTypeLabel(type?: string) {
    const known = formFieldsList.find((f) => f.type === type);
    if (known) return known.name;
    return (type ?? 'Field').replaceAll('_', ' ').toLowerCase();
}

const SlideBuilder = ({ slide, isScaledDown = false, disabled = false }: { slide: StandardFormFieldDto; isScaledDown?: boolean; disabled?: boolean }) => {
    const slideFields = slide?.properties?.fields;
    const { deleteField, duplicateField, updateSlideSectionTitle } = useFormFieldsAtom();
    const { setActiveFieldComponent, activeFieldComponent } = useActiveFieldComponent();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { theme } = useFormState();
    const logo = useBuilderFormLogo();
    const { navbarState, setNavbarState } = useNavbarState();
    // Plain-language tips use the form's declared language when it has one.
    const form = useAppSelector(selectForm);
    const plainLanguage = { formId: form?.formId, formLanguage: form?.settings?.language };
    // Leaflet (WYSIWYG with the respondent page): the numbered section bar,
    // the opening text block on the intro band, n.m numbers in the margin.
    // The canvas shows every field, so numbering follows the page's order.
    const leaflet = styleTokens(theme?.style).key === 'leaflet';
    const emptyLabel = `Section ${(slide?.index ?? 0) + 1}`;
    // The page's own section title wins; without one the bar falls back to
    // the opening heading, then the first question (utils/leaflet-sections.ts).
    const ownTitle = pageSectionTitle(slide);
    const [editingBarTitle, setEditingBarTitle] = useState(false);
    const section = leaflet ? leafletSection(slideFields ?? [], emptyLabel, ownTitle) : null;
    const fallbackTitle = leaflet ? leafletSection(slideFields ?? [], emptyLabel).shortTitle : '';
    const numbers = leaflet ? questionNumbers(slideFields ?? [], (slide?.index ?? 0) + 1) : {};
    const numberInk = actionInk(theme);
    // The page's opening text block is edited where respondents see it: its
    // heading as the title on the navy section bar, the rest on the intro
    // band (one editor, dressed per block), instead of a second copy below.
    // With a section title of its own (or while one is being typed) the bar
    // edits that title and the heading stays in the band.
    const opening = leaflet && slideFields?.[0]?.type === FieldTypes.TEXT ? slideFields[0]! : null;
    const openingDoc = opening && typeof opening.title === 'object' ? (opening.title as any) : null;
    const headingOnBar = !ownTitle && !editingBarTitle && !!openingDoc && openingDoc.content?.[0]?.type === 'heading';
    const barTitleEditor =
        !disabled && !isScaledDown && slide?.index !== undefined ? (
            <SectionTitleInput value={slide.properties?.sectionTitle ?? ''} placeholder={fallbackTitle} onChange={(value) => updateSlideSectionTitle(slide.index, value)} onFocusChange={setEditingBarTitle} />
        ) : undefined;
    const sectionNumber = (slide?.index ?? 0) + 1;
    const marginVar = leaflet ? ({ ['--leaflet-margin' as string]: `${leafletMarginWidth(numbers, sectionNumber)}px` } as React.CSSProperties) : undefined;
    const selectOpening = (event: React.SyntheticEvent) => {
        event.stopPropagation();
        if (opening) setActiveFieldComponent({ id: opening.id, index: 0 });
    };

    return (
        <SlideLayoutWrapper showDesktopLayout slide={slide} disabled={disabled} theme={theme} scrollDivId={!disabled ? 'scroll-div' : undefined} topAligned={leaflet} logo={logo}>
            {leaflet && section && (
                <div style={marginVar}>
                    <LeafletTopRule theme={theme} />
                    {!headingOnBar && <LeafletSectionBar theme={theme} numeral={sectionNumber} title={section.shortTitle} fullTitle={section.title} layout={slide.properties?.layout} titleEditor={barTitleEditor} />}
                    {opening && (
                        <div
                            // Full width like the respondent's bar and band; the
                            // heading's navy reaches the page edges through a
                            // filled border image (no box, no shadow), clipped here.
                            className={cn('-mx-5 overflow-x-clip px-5 sm:-mx-8 sm:px-8', !headingOnBar && 'py-4')}
                            style={{ background: leafletColours(theme).band, color: theme?.primary }}
                            data-testid="leaflet-canvas-opening"
                        >
                            <div
                                tabIndex={-1}
                                onClick={selectOpening}
                                onFocus={selectOpening}
                                className={cn(
                                    FORM_COLUMN,
                                    columnPlacementClass(slide.properties?.layout),
                                    'relative cursor-text',
                                    activeFieldComponent?.id === opening.id && 'outline-2 outline-offset-2 outline-[#123FC9]',
                                    headingOnBar &&
                                        '[&_.ProseMirror]:leading-[1.6] [&_.ProseMirror>*:first-child]:relative [&_.ProseMirror>*:first-child]:py-3.5 [&_.ProseMirror>*:first-child]:pl-[var(--leaflet-margin,34px)] [&_.ProseMirror>*:first-child]:font-(family-name:--leaflet-serif) [&_.ProseMirror>*:first-child]:text-[22px]! [&_.ProseMirror>*:first-child]:leading-[1.25]! [&_.ProseMirror>*:first-child]:font-semibold! [&_.ProseMirror>*:first-child]:text-white [&_.ProseMirror>*:first-child]:[border-image:conic-gradient(var(--leaflet-bar)_0_0)_fill_0//0_100vmax] [&_.ProseMirror>*:first-child]:before:absolute [&_.ProseMirror>*:first-child]:before:top-3.5 [&_.ProseMirror>*:first-child]:before:left-0 [&_.ProseMirror>*:first-child]:before:text-[28px] [&_.ProseMirror>*:first-child]:before:leading-none [&_.ProseMirror>*:first-child]:before:tabular-nums [&_.ProseMirror>*:first-child]:before:content-(--leaflet-numeral) [&_.ProseMirror>*:last-child:not(:first-child)]:mb-4 [&_.ProseMirror>*:nth-child(2)]:mt-4!'
                                )}
                                style={
                                    {
                                        '--leaflet-bar': theme?.secondary,
                                        '--leaflet-serif': leafletSerif.style.fontFamily,
                                        '--leaflet-numeral': `"${sectionNumber}"`
                                    } as React.CSSProperties
                                }
                            >
                                <RichTextEditor field={opening} slide={slide} />
                            </div>
                        </div>
                    )}
                </div>
            )}
            {/* WYSIWYG: the same form column, 48px question rhythm and
                vertical placement as the respondent page (form-column.ts);
                pt-12 matches the space the respondent page keeps for its
                header bar. */}
            <div className={cn('w-full', leaflet ? 'pt-7' : 'pt-12')} style={marginVar}>
                <div
                    className={cn(
                        FORM_COLUMN,
                        // Page alignment positions the column, not each field.
                        columnPlacementClass(slide.properties?.layout),
                        'flex flex-col gap-12 lg:grid lg:grid-cols-12 lg:gap-x-6 lg:gap-y-12'
                    )}
                >
                    <AnimatePresence>
                        {Array.isArray(slideFields) && slideFields.length ? (
                            slideFields.map((field, index) => {
                                if (opening && field.id === opening.id) return null;
                                // Tips show for the question being edited only, so the canvas stays calm.
                                const showHints = !disabled && !isScaledDown && activeFieldComponent?.id === field.id;
                                const titleHintsId = `plain-language-title-${field.id}`;
                                const number = numbers[field.id];
                                return (
                                    <motion.div
                                        key={field.id}
                                        {...({
                                            initial: { x: navbarState.insertClicked && activeSlideComponent?.id === slide.id ? '-10%' : 0 },
                                            animate: { x: 0 },
                                            transition: { duration: 0.5 },
                                            id: disabled ? field.id : `scroll-field-${field.id}`,
                                            // WYSIWYG: the canvas packs columns exactly like the runtime.
                                            style: { gridColumn: `span ${clampSpan(field)} / span ${clampSpan(field)}` },
                                            // Rows size to content — h-full made every row stretch to an
                                            // equal share of the slide, so spacing changed with field count.
                                            className: cn('relative flex w-full min-w-0 flex-row items-center', fieldSpacingClass(field, index === slideFields.length - 1))
                                        } as any)}
                                    >
                                        <div
                                            key={index}
                                            tabIndex={0}
                                            className={cn(activeFieldComponent?.id === field.id && 'rounded-lg ring-2 ring-[#123FC9]', 'w-full cursor-pointer p-1')}
                                            onFocus={(event) => {
                                                event.preventDefault();
                                                event.stopPropagation();
                                                setActiveFieldComponent({
                                                    id: field.id,
                                                    index: index
                                                });
                                            }}
                                            onClick={(event) => {
                                                event.preventDefault();
                                                event.stopPropagation();
                                                setActiveFieldComponent({
                                                    id: field.id,
                                                    index: index
                                                });
                                            }}
                                        >
                                            <div className={'relative flex flex-col items-start'}>
                                                {!isScaledDown && field.internal && (
                                                    <div
                                                        className="absolute -top-6 left-0 z-10 inline-flex items-center gap-1 rounded bg-black-200 px-1.5 py-[2px] text-[10px] font-semibold text-black-700"
                                                        title="Respondents never see this field — your team fills it in on each response"
                                                    >
                                                        <LockIcon className="h-3 w-3" aria-hidden="true" />
                                                        Internal · staff only
                                                    </div>
                                                )}
                                                {!isScaledDown && !field.internal && fieldHasLogic(field) && (
                                                    <div
                                                        className="absolute -top-6 left-0 z-10 inline-flex items-center gap-1 rounded bg-brand-100 px-1.5 py-[2px] text-[10px] font-semibold text-brand-500"
                                                        title="This field is shown/hidden by a logic rule"
                                                    >
                                                        <LogicOutlinedIcon className="h-3 w-3" />
                                                        Logic
                                                    </div>
                                                )}
                                                {!isScaledDown && activeFieldComponent && activeFieldComponent?.id === field.id && (
                                                    // Selection toolbar: what this field is, then what you can do
                                                    // with it. Delete is last and quiet-red — a destructive action
                                                    // shouldn't be the selection's only (or loudest) affordance.
                                                    <div className="absolute -top-12 right-0 z-10 flex items-center overflow-hidden rounded border border-black-300 bg-white shadow-large">
                                                        <span className="px-2.5 text-[11px] font-semibold tracking-wide text-black-600 uppercase">{fieldTypeLabel(field.type)}</span>
                                                        <span className="h-5 w-px bg-black-400" aria-hidden="true" />
                                                        <button
                                                            type="button"
                                                            title="Duplicate question"
                                                            className="p-2 text-black-700 hover:bg-black-100"
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                duplicateField(slide.index, index);
                                                            }}
                                                        >
                                                            <Copy width={16} height={16} />
                                                        </button>
                                                        <button
                                                            type="button"
                                                            title="Delete question"
                                                            className="p-2 text-[#C43D3D] hover:bg-[#FBEFEF]"
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                deleteField(slide.index, index);
                                                            }}
                                                        >
                                                            <Trash width={16} height={16} />
                                                        </button>
                                                    </div>
                                                )}
                                                {activeFieldComponent?.id === field.id && (
                                                    <div className={cn('absolute -left-10 -mt-1 text-black-600', '', isScaledDown ? 'hidden' : '')}>
                                                        <MoveUpDown slideIndex={slide.index} field={field} />
                                                    </div>
                                                )}
                                                <div className={cn('mb-2 w-full', number && '[&>*:not(:first-child)]:pl-[var(--leaflet-margin,34px)]')}>
                                                    <div className={cn('relative w-full', number ? 'grid grid-cols-[var(--leaflet-margin,34px)_minmax(0,1fr)] items-baseline' : 'flex items-center gap-2')}>
                                                        {number && (
                                                            <span aria-hidden="true" className="text-[16px] leading-[1.4] tabular-nums" style={{ fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: numberInk }}>
                                                                {number}
                                                            </span>
                                                        )}
                                                        {!leaflet && slide?.properties?.showQuestionNumbers && <span className="text-2xl">{index + 1}.</span>}
                                                        <RichTextEditor
                                                            field={field}
                                                            slide={slide}
                                                            // autofocus={field?.type !== FieldType.MATRIX && activeFieldComponent?.id === field.id}
                                                            isRequired={field?.validations?.required}
                                                            describedById={titleHintsId}
                                                        />
                                                    </div>
                                                    {showHints && <PlainLanguageHints id={titleHintsId} value={field.title} {...plainLanguage} />}
                                                    <FieldDescription field={field} disabled={disabled} hints={showHints ? plainLanguage : undefined} />
                                                </div>
                                                <div className={cn('w-full', number && 'pl-[var(--leaflet-margin,34px)]')}>{renderFieldWrapper(field, slide, disabled)}</div>
                                            </div>
                                        </div>
                                    </motion.div>
                                );
                            })
                        ) : !disabled && !isScaledDown ? (
                            // An empty page shouldn't be a dead rectangle — give
                            // first-run creators a direct way in (audit B4).
                            <div className="flex h-full w-full items-center justify-center lg:col-span-12">
                                <button
                                    type="button"
                                    className="flex flex-col items-center gap-2 rounded border border-dashed border-black-400 bg-white/60 px-10 py-8 text-sm font-medium text-black-700 transition-colors hover:border-black-600 hover:text-black-900"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        setNavbarState({ ...navbarState, insertMenuOpen: true });
                                    }}
                                >
                                    <span className="text-2xl leading-none">＋</span>
                                    Add a question
                                    <span className="text-xs font-normal text-black-600">Pick a field type from the Insert menu</span>
                                </button>
                            </div>
                        ) : (
                            <></>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </SlideLayoutWrapper>
    );
};
export default SlideBuilder;
