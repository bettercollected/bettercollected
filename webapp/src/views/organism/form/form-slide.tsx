'use client';

import { Shield } from 'lucide-react';
import { Controller } from 'react-scrollmagic';

import { FormTheme } from '@app/constants/theme';
import { useDerivedAnswers } from '@app/lib/hooks/use-derived-answers';
import { statesFor, useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import { useClearUnavailableOptions, useOptionStates } from '@app/lib/hooks/use-option-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import SaveDraftControl from '@app/components/drafts/save-draft-control';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { resolvePipesInTitle } from '@app/utils/answer-piping';
import { isShownToRespondents } from '@app/utils/calculated-fields';
import { getHiddenFieldIds, logicSourcesById, resolveJump } from '@app/utils/conditional-logic';
import { ResolvedFormLogo } from '@app/utils/form-logo';
import { leafletMarginWidth, leafletSection, questionNumbers } from '@app/utils/leaflet-sections';
import { pageInvalidations } from '@app/utils/page-validation';
import { hasSeveralPages, plainQuestionNumbers } from '@app/utils/question-numbering';
import { isRepeatingGroup, parseScopedFieldId } from '@app/utils/repeating-groups';
import { isReviewEnabled, walkReviewPath } from '@app/utils/review-page';
import { focusQuestionInGroup, scrollToDivById } from '@app/utils/scroll-utils';
import { actionText } from '@app/utils/theme-contrast';
import { workspaceDisplayName } from '@app/utils/workspace-display-name';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';
import BackButton from '@app/views/molecules/form-builder/back-button';
import { LeafletIntroBand, LeafletSectionBar, leafletNumbersHang } from '@app/views/molecules/form/leaflet-section';
import AddressField from '@app/views/molecules/responder-form-fields/address-field';
import CalculatedField from '@app/views/molecules/responder-form-fields/calculated-field';
import CurrencyField from '@app/views/molecules/responder-form-fields/currency-field';
import DateField from '@app/views/molecules/responder-form-fields/date-field';
import DateRangeField from '@app/views/molecules/responder-form-fields/date-range-field';
import DayField from '@app/views/molecules/responder-form-fields/day-field';
import SignatureField from '@app/views/molecules/responder-form-fields/signature-field';
import TagsField from '@app/views/molecules/responder-form-fields/tags-field';
import TimeField from '@app/views/molecules/responder-form-fields/time-field';
import DropDownField from '@app/views/molecules/responder-form-fields/drop-down-field';
import FieldRuleAnnouncer from '@app/views/molecules/responder-form-fields/field-rule-announcer';
import FileUploadField from '@app/views/molecules/responder-form-fields/file-upload-field';
import InputField from '@app/views/molecules/responder-form-fields/input-field';
import LinearRatingField from '@app/views/molecules/responder-form-fields/linear-rating';
import MultipleChoiceField from '@app/views/molecules/responder-form-fields/multiple-choice-field';
import MultipleChoiceWithMultipleSelection from '@app/views/molecules/responder-form-fields/multiple-choice-with-multiple-selections';
import SourceOptionsField from '@app/views/molecules/responder-form-fields/source-options-field';
import PhoneNumberField from '@app/views/molecules/responder-form-fields/phone-number-field';
import { PreviewModeContext } from '@app/views/molecules/responder-form-fields/preview-mode-context';
import { QuestionNumberContext } from '@app/views/molecules/responder-form-fields/question-number-context';
import QuestionWrapper from '@app/views/molecules/responder-form-fields/question-wrapper';
import RatingField from '@app/views/molecules/responder-form-fields/rating-field';
import RepeatingGroupField from '@app/views/molecules/responder-form-fields/repeating-group-field';
import TabularInputResponderField from '@app/views/molecules/responder-form-fields/tabular-input-responder-field';
import TextAreaField from '@app/views/molecules/responder-form-fields/text-area-field';
import YesNoField from '@app/views/molecules/responder-form-fields/yes-no-field';
import { formButtonStyle } from '@app/views/molecules/theme/theme-root';
import { contrast, leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';

import ImageField from '../form-builder/fields/image-field';
import MatrixField from '../form-builder/fields/matrix';
import VideoField from '../form-builder/fields/video-field';
import { FORM_COLUMN, FORM_GUTTER, clampSpan, columnPlacementClass, fieldSpacingClass } from '../layout/form-column';
import SlideLayoutWrapper from '../layout/slide-layout-wrapper';
import ShareIdentityConsent from './share-identity-consent';
import { submitErrorKey, useEmitFlow, useFinishForm } from './use-finish-form';

// A #rrggbb page colour at ~90% opacity; anything else (unset, named colours)
// falls back to a translucent white.
export function headerGround(accent?: string, background?: FormTheme['background']) {
    // Over a plain colour or a pattern (margin, columns, dots...) the bar is the
    // page colour, opaque: a 90% bar lets the questions scrolling under it show
    // through its text. Gradients and images keep the translucent, blurred bar.
    const solid = !background || background.type === 'color' || background.type === 'pattern';
    if (solid && accent && /^#[0-9a-fA-F]{6}$/.test(accent)) return accent;
    return accent && /^#[0-9a-fA-F]{6}$/.test(accent) ? `${accent}E6` : 'rgba(255,255,255,0.85)';
}

export function FormFieldComponent({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    switch (field.type) {
        case FieldTypes.TEXT:
            return <QuestionWrapper field={field} />;
        case FieldTypes.EMAIL:
        case FieldTypes.NUMBER:
        case FieldTypes.LINK:
            return <InputField field={field} />;
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LONG_TEXT:
            return <TextAreaField field={field} />;
        case FieldTypes.MULTIPLE_CHOICE:
            // options from a list or another form's answers: a searchable list, fetched as the respondent uses it
            if (field?.properties?.optionSource) return <SourceOptionsField field={field} slideIndex={slideIndex} />;
            if (field?.properties?.allowMultipleSelection) {
                return <MultipleChoiceWithMultipleSelection field={field} slideIndex={slideIndex} />;
            }
            return <MultipleChoiceField field={field} slideIndex={slideIndex} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} />;
        case FieldTypes.FILE_UPLOAD:
            return <FileUploadField field={field} />;
        case FieldTypes.DROP_DOWN:
            if (field?.properties?.optionSource) return <SourceOptionsField field={field} slideIndex={slideIndex} />;
            return <DropDownField field={field} slideIndex={slideIndex} />;
        case FieldTypes.PHONE_NUMBER:
            return <PhoneNumberField field={field} />;
        case FieldTypes.RATING:
            return <RatingField field={field} />;
        case FieldTypes.DATE:
            return <DateField field={field} />;
        case FieldTypes.DAY:
            return <DayField field={field} />;
        case FieldTypes.TIME:
            return <TimeField field={field} />;
        case FieldTypes.CURRENCY:
            return <CurrencyField field={field} />;
        case FieldTypes.DATE_RANGE:
            return <DateRangeField field={field} />;
        case FieldTypes.TAGS:
            return <TagsField field={field} />;
        case FieldTypes.ADDRESS:
            return <AddressField field={field} />;
        case FieldTypes.SIGNATURE:
            return <SignatureField field={field} />;
        case FieldTypes.LINEAR_RATING:
            return <LinearRatingField field={field} />;
        case FieldTypes.IMAGE_CONTENT:
            return <ImageField field={field} />;
        case FieldTypes.VIDEO_CONTENT:
            return <VideoField field={field} />;
        case FieldTypes.MATRIX:
            return (
                // Rows of radio groups (or checkboxes): one group named by the question.
                <QuestionWrapper field={field} group>
                    <MatrixField field={field} />
                </QuestionWrapper>
            );
        case FieldTypes.TABULAR_INPUT:
            return <TabularInputResponderField field={field} />;
        case FieldTypes.CALCULATED:
            return <CalculatedField field={field} />;
        case FieldTypes.GROUP:
            if (isRepeatingGroup(field)) return <RepeatingGroupField field={field} renderChild={(child) => <FormFieldComponent field={child} slideIndex={slideIndex} />} />;
            return <QuestionWrapper field={field} />;
        default:
            return <QuestionWrapper field={field} />;
    }
}

export default function FormSlide({ index, formSlideData, isPreviewMode = false, showDesktopLayout, logo }: { index: number; isPreviewMode: boolean; formSlideData?: any; showDesktopLayout?: boolean; logo?: ResolvedFormLogo | null }) {
    const { toast } = useToast();
    const { t, language } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const standardForm = useAppSelector(selectResponderForm);
    // undefined once the form came back without its questions (closed)
    const formSlideFromState = standardForm?.fields?.[index];
    const formSlide = formSlideData ? formSlideData : formSlideFromState;

    const { currentSlide, nextSlide, goToSlide, previousSlide, setCurrentSlideToWelcomePage, goToReview, returnToReview, continueFrom, responderState } = useResponderState();

    const { formResponse, setInvalidFields } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    // Calculated fields, and the values field rules set or lock, follow the
    // answers live (logic, jumps and piping read them).
    useDerivedAnswers(standardForm?.fields, standardForm?.hiddenFields);
    // What the rules decide now: effective Required, locked questions.
    const ruleStates = useFieldRuleStates();
    // Options the form's option logic no longer offers are cleared from the
    // answers (the question says so), and a question with nothing to choose
    // is not required.
    useClearUnavailableOptions(standardForm?.fields);
    const optionStates = useOptionStates();
    const workspace = useAppSelector(selectWorkspace);
    const authState = useAppSelector(selectAuth);
    // Sending the form (here on the last page, or from the review page), and what shows when it fails.
    const { finishForm, isLoading, submitError, setSubmitError, effectiveAnonymize } = useFinishForm(isPreviewMode);
    const emitFlow = useEmitFlow(isPreviewMode);
    // With a review page the form is not sent from here: the last page goes on to the review.
    const reviewOn = isReviewEnabled(standardForm);
    const finishOrReview = (endingId?: string) => (reviewOn ? goToReview(endingId) : finishForm(endingId));

    // The form's questions by id: a condition on a choice question reads its
    // options from them (answers hold option ids, conditions an option's text).
    const logicSources = logicSourcesById(standardForm?.fields);
    // Fields hidden by conditional logic given the answers so far. Recomputed each
    // render, so the form reacts live as the responder answers earlier questions.
    const hiddenFieldIds = getHiddenFieldIds(formSlide?.properties?.fields, formResponse.answers || {}, logicSources);
    // Calculations kept from respondents ("internal results") are computed, never shown.
    const visibleFields: StandardFormFieldDto[] = (formSlide?.properties?.fields || []).filter((field: StandardFormFieldDto) => !hiddenFieldIds.has(field.id) && isShownToRespondents(field));

    // Leaflet: the page is a numbered section (its position in the form, the
    // same number "Page x of y" shows) and its questions are numbered among
    // the ones visible now (utils/leaflet-sections.ts).
    const leaflet = styleTokens(standardForm?.theme?.style).key === 'leaflet';
    const pageLayout = formSlide?.properties?.layout;
    const section = leaflet
        ? leafletSection(
              visibleFields.map((field, position) =>
                  position === 0 && field.type === FieldTypes.TEXT ? { ...field, title: resolvePipesInTitle(field.title, { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues }) as any } : field
              ),
              t('LEAFLET.SECTION', { n: index + 1 }),
              formSlide?.properties?.sectionTitle
          )
        : null;
    const pageFields = section?.openingTextId ? visibleFields.filter((field) => field.id !== section.openingTextId) : visibleFields;
    // Leaflet always numbers its questions; other styles when the form has
    // question numbering on (utils/question-numbering.ts).
    const numbering = leaflet
        ? { numbers: questionNumbers(pageFields, index + 1), hang: leafletNumbersHang(pageLayout) }
        : formSlide?.properties?.showQuestionNumbers
          ? { numbers: plainQuestionNumbers(pageFields, index + 1, hasSeveralPages(standardForm?.fields)), hang: false, plain: true }
          : null;
    const theme = standardForm?.theme;
    const marginVar = numbering ? ({ ['--leaflet-margin' as string]: `${leafletMarginWidth(numbering.numbers, index + 1)}px` } as React.CSSProperties) : undefined;
    // The header's words in the action colour where it reads as text on the page.
    const leafletHeaderInk = theme?.secondary && theme?.accent && contrast(theme.secondary, theme.accent) >= 4.5 ? theme.secondary : theme?.primary;

    // Where "Next" goes with the answers so far: a jump that submits makes
    // this page the last one, whatever its place in the form.
    const isLastPage = (standardForm?.fields?.length || 0) - 1 === currentSlide && currentSlide === index;
    const endsHere = currentSlide === index && resolveJump(formSlide, formResponse.answers || {}, logicSources)?.target === JUMP_TARGET_SUBMIT;
    const submitsHere = isLastPage || endsHere;
    // Editing this page from the review page: the way back to it.
    const backToReviewOffered = responderState.reviewPath?.includes(index) && currentSlide === index;

    // This page is complete, or says what is not (focus goes to the first question with a problem).
    const pageIsComplete = (): boolean => {
        setSubmitError(false);
        const invalidations = pageInvalidations(formSlide, standardForm?.fields, formResponse.answers || {}, ruleStates, logicSources, optionStates);
        setInvalidFields(invalidations);
        if (Object.keys(invalidations).length === 0) return true;
        // Every key is the id of the element to bring into view; questions
        // inside a group item sit in nested containers, so let the browser
        // find their scroll position.
        const firstKey = Object.keys(invalidations)[0];
        // Focus goes to the first question with a problem, so a keyboard or
        // screen reader user lands on it and hears its error.
        if (parseScopedFieldId(firstKey)) focusQuestionInGroup(firstKey);
        else scrollToDivById(firstKey, undefined, { focusControl: true });
        return false;
    };

    // "Back to review": this page, then the pages after it on the reviewed path,
    // are replayed with the new answers (utils/review-page.ts walkReviewPath). Where
    // nothing changed the respondent is back on the review; where an edit changed
    // the way through the form they carry on from there.
    const onBackToReview = () => {
        if (!pageIsComplete()) return;
        const path = responderState.reviewPath ?? [];
        const answers = formResponse.answers || {};
        const states = statesFor(standardForm?.fields, answers, hiddenValues, standardForm?.hiddenFields, path);
        const walk = walkReviewPath({ slides: standardForm?.fields, answers, path, states });
        if (walk.kind === 'review') returnToReview(walk.path, walk.endingId);
        else if (walk.kind === 'continue') continueFrom(walk.path, walk.target);
        else {
            // a page after this one is not complete any more: there, with what it lacks marked
            continueFrom(walk.path, walk.page);
            setInvalidFields(pageInvalidations(standardForm?.fields?.[walk.page], standardForm?.fields, answers, states, logicSources, optionStates));
        }
    };

    const onNext = () => {
        if (!pageIsComplete()) return;

        // Page-jump / branching: a matching rule overrides the linear next page.
        const jump = resolveJump(formSlide, formResponse.answers || {}, logicSources);
        const jumpTargetId = jump?.target || null;
        if (jumpTargetId === JUMP_TARGET_SUBMIT) {
            if (isPreviewMode) toast({ description: 'Logic rule matched → submitting the form' });
            // (with a review page the submit, and its breadcrumb, are the review's)
            if (!reviewOn) emitFlow(formSlide.id, '__submit__');
            finishOrReview(jump?.endingId || undefined);
            return;
        }
        if (jumpTargetId) {
            const targetIndex = standardForm?.fields?.findIndex((s) => s.id === jumpTargetId) ?? -1;
            if (targetIndex >= 0) {
                if (isPreviewMode) toast({ description: `Logic rule matched → jumped to Page ${targetIndex + 1}` });
                emitFlow(formSlide.id, jumpTargetId);
                goToSlide(targetIndex);
                return;
            }
        }

        if (currentSlide + 1 === standardForm?.fields?.length) {
            if (!reviewOn) emitFlow(formSlide.id, '__submit__');
            finishOrReview();
        } else {
            emitFlow(formSlide.id, standardForm?.fields?.[currentSlide + 1]?.id ?? '__next__');
            nextSlide();
        }
    };

    if (!formSlide) return <FullScreenLoader />;

    return (
        <Controller>
            <SlideLayoutWrapper showDesktopLayout={showDesktopLayout} scrollDivId={'questions-container'} theme={standardForm.theme} slide={formSlide} disabled topAligned={leaflet} logo={logo}>
                {/* The page's top heading, for screen-reader users moving by
                    headings: the form's title, which the welcome page shows. */}
                {standardForm?.title && (
                    <h1 className="sr-only" lang={contentLang}>
                        {standardForm.title}
                    </h1>
                )}
                {/* What the form's field rules changed on this page, said once, politely. */}
                <FieldRuleAnnouncer fields={pageFields} />
                {/* The bar sits over the scrolling questions: give it the page's
                    ground (translucent + blur, so it also works over gradient or image
                    backgrounds) or questions scroll through the header text. */}
                <div
                    className={cn('backdrop-blur-sm absolute top-0 right-0 left-0 z-10 mx-auto w-full', leaflet ? 'flex h-14 items-center border-b' : 'pt-5 pb-3')}
                    style={{
                        background: headerGround(formSlide?.properties?.theme?.accent || standardForm?.theme?.accent, (formSlide?.properties?.theme || standardForm?.theme)?.background),
                        ...(leaflet ? { borderColor: leafletColours(theme).rule, background: formSlide?.properties?.theme?.accent || theme?.accent || '#ffffff' } : {})
                    }}
                >
                    {/* Same gutter and column as the questions below, so Back
                        and the progress line up with the fields' edges. */}
                    <div className={cn(FORM_GUTTER, 'w-full')}>
                        <div className={cn(FORM_COLUMN, columnPlacementClass(formSlide?.properties?.layout), 'flex items-center justify-between gap-3')}>
                            <BackButton
                                label={t('NAV.BACK')}
                                handleClick={() => {
                                    currentSlide > 0 ? previousSlide() : setCurrentSlideToWelcomePage();
                                }}
                                // -ml-1.5 puts the chevron, not the button's padding, on the column edge;
                                // 44px tall, a full touch target.
                                className="-ml-1.5 min-h-11 w-fit bg-inherit!"
                                style={{
                                    background: standardForm?.theme?.accent,
                                    // The theme's ink, not a fixed grey: a fixed neutral fell
                                    // under 4.5:1 on tinted grounds (4.09:1 on Ocean).
                                    color: leaflet ? leafletHeaderInk : standardForm?.theme?.primary
                                }}
                            />
                            {/* Provenance + progress where the eye starts (DESIGN.md §3):
                                who is asking, and how much is left — no surprises. */}
                            <div className="flex items-center gap-3 text-[13px]" style={{ color: leaflet ? leafletHeaderInk : standardForm?.theme?.primary }}>
                                {workspaceDisplayName(workspace) && (
                                    <span className="hidden items-center gap-1.5 rounded-full border border-black-400 bg-white/85 px-2.5 py-0.5 font-medium text-black-800 sm:inline-flex">
                                        <Shield className="h-3.5 w-3.5 text-brand-500" strokeWidth={1.8} aria-hidden="true" />
                                        {workspaceDisplayName(workspace)}
                                    </span>
                                )}
                                {/* Where focus lands when this page opens (form.tsx focusPageStart). */}
                                <span data-page-start tabIndex={-1} className="font-medium whitespace-nowrap tabular-nums outline-none" lang={language}>
                                    {endsHere && !isLastPage ? t('NAV.LAST_PAGE') : t('NAV.PAGE_OF', { current: Math.min(Math.max(currentSlide, 0) + 1, standardForm?.fields?.length || 1), total: standardForm?.fields?.length || 1 })}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
                {/* Leaflet: the numbered section bar and the intro band, full
                    width, straight under the header (pt-14 clears it). */}
                {leaflet && section && (
                    <div className="pt-14" style={marginVar}>
                        <LeafletSectionBar theme={theme} numeral={index + 1} title={section.shortTitle} fullTitle={section.title} layout={pageLayout} lang={section.source === 'empty' ? undefined : contentLang} />
                        {section.intro && (
                            <LeafletIntroBand theme={theme} layout={pageLayout}>
                                <FormFieldComponent field={section.intro} slideIndex={formSlide!.index} />
                            </LeafletIntroBand>
                        )}
                    </div>
                )}
                {/* The page's questions in the form column (form-column.ts); the
                    layout wrapper centres a short page vertically and lets a long
                    one scroll from the top. pt-12 clears the header bar above.
                    48px between questions (~6× the 8px inside a question). */}
                <div className={cn(FORM_COLUMN, columnPlacementClass(formSlide?.properties?.layout), 'relative flex flex-col lg:grid lg:grid-cols-12 lg:gap-x-6', leaflet ? 'gap-10 pt-7 lg:gap-y-10' : 'gap-12 pt-12 lg:gap-y-12')} style={marginVar}>
                    <QuestionNumberContext.Provider value={numbering}>
                        <PreviewModeContext.Provider value={isPreviewMode}>
                        {pageFields.map((field: StandardFormFieldDto, position: number) => (
                            // 12-grid width on desktop: adjacent spans that fit pack
                            // into one row (two 6s sit side by side); mobile stays a
                            // flex column, where the span style is inert.
                            <div key={field.id} className={cn('min-w-0', fieldSpacingClass(field, position === pageFields.length - 1))} style={{ gridColumn: `span ${clampSpan(field)} / span ${clampSpan(field)}` }}>
                                <FormFieldComponent field={field} slideIndex={formSlide!.index} />
                            </div>
                        ))}
                        </PreviewModeContext.Provider>
                    </QuestionNumberContext.Provider>
                    {/* The button belongs to the last answer: 32px above it,
                        a little closer than the 48px between questions. */}
                    <div
                        // Leaflet: the button lines up with the question text, past the margin column.
                        className={cn('-mt-4 flex flex-col items-start gap-4', leaflet && 'ml-[var(--leaflet-margin,34px)]', leaflet && numbering?.hang && '@min-[880px]/page:ml-0')}
                        style={{ gridColumn: 'span 12 / span 12' }}
                    >
                        {/* With a review page the respondent sends from there, with this choice beside the button. */}
                        {submitsHere && !reviewOn && <ShareIdentityConsent effectiveAnonymize={effectiveAnonymize} />}
                        <div className="flex flex-wrap items-center gap-3">
                            {/* Editing from the review page: back to it is the main way on; Continue still walks the pages in order. */}
                            {backToReviewOffered && (
                                <Button
                                    flat
                                    style={formButtonStyle(standardForm.theme?.secondary, leaflet ? '4px' : '8px')}
                                    className={cn('form-button min-h-12 px-8 py-3 text-base font-semibold', leaflet ? 'rounded-[4px]' : 'rounded-[8px]')}
                                    onClick={onBackToReview}
                                    size="medium"
                                    data-testid="back-to-review"
                                >
                                    {t('REVIEW.BACK_TO_REVIEW')}
                                </Button>
                            )}
                            <Button
                                flat
                                // Filled with the action colour unless the theme's button style says otherwise (theme-root.ts).
                                style={
                                    backToReviewOffered
                                        ? { color: actionText(theme), borderColor: 'currentColor', borderRadius: `var(--form-radius-button, ${leaflet ? '4px' : '8px'})` }
                                        : formButtonStyle(standardForm.theme?.secondary, leaflet ? '4px' : '8px')
                                }
                                variant={backToReviewOffered ? 'ghost' : undefined}
                                isLoading={isLoading}
                                className={cn('form-button min-h-12 px-8 py-3 text-base font-semibold', backToReviewOffered && 'border-2 bg-transparent', leaflet ? 'rounded-[4px]' : 'rounded-[8px]')}
                                onClick={onNext}
                                size="medium"
                            >
                                {submitsHere && !reviewOn ? t('NAV.SUBMIT') : submitsHere ? t('REVIEW.GO_TO_REVIEW') : t('NAV.CONTINUE')}
                            </Button>
                        </div>
                        {/* "Save and continue later", when the form lets respondents (not in the builder's preview). */}
                        {!isPreviewMode && <SaveDraftControl ink={leaflet ? leafletHeaderInk : standardForm?.theme?.primary} />}
                        {/* Stays until the next attempt; the toast alone is gone in a moment. */}
                        {submitError && (
                            <p role="alert" className="text-[15px] leading-relaxed font-medium text-[#B42318]" lang={language}>
                                {t(submitErrorKey(submitError))}
                            </p>
                        )}
                    </div>
                </div>
            </SlideLayoutWrapper>
        </Controller>
    );
}
