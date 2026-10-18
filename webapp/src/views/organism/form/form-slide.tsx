'use client';

import { useState } from 'react';

import { Shield } from 'lucide-react';
import { Controller } from 'react-scrollmagic';

import { useCalculatedFields } from '@app/lib/hooks/use-calculated-fields';
import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { useSendFlowEventMutation, useSubmitResponseMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { aiNoticeTokenToSend } from '@app/utils/ai-notice';
import { getInputFieldsById, resolvePipesInTitle } from '@app/utils/answer-piping';
import { validateAnswerRulesInSlide } from '@app/utils/answer-rules';
import { isShownToRespondents, localToday } from '@app/utils/calculated-fields';
import { getHiddenFieldIds, resolveJump } from '@app/utils/conditional-logic';
import { validateDateRulesInSlide } from '@app/utils/date-rules';
import { getFlowSessionId } from '@app/utils/flow-session';
import { ResolvedFormLogo } from '@app/utils/form-logo';
import { leafletMarginWidth, leafletSection, questionNumbers } from '@app/utils/leaflet-sections';
import { hasSeveralPages, plainQuestionNumbers } from '@app/utils/question-numbering';
import { isRepeatingGroup, normalizeGroupAnswersForSubmit, parseScopedFieldId, validateGroupsInSlide } from '@app/utils/repeating-groups';
import { scrollToDivById } from '@app/utils/scroll-utils';
import { firstPageWithError, historyBackTo, serverAnswerErrors, serverInvalidations } from '@app/utils/server-answer-errors';
import { validateSlide } from '@app/utils/vvalidation-utils';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';
import BackButton from '@app/views/molecules/form-builder/back-button';
import { LeafletIntroBand, LeafletSectionBar, leafletNumbersHang } from '@app/views/molecules/form/leaflet-section';
import CalculatedField from '@app/views/molecules/responder-form-fields/calculated-field';
import DateField from '@app/views/molecules/responder-form-fields/date-field';
import DropDownField from '@app/views/molecules/responder-form-fields/drop-down-field';
import FileUploadField from '@app/views/molecules/responder-form-fields/file-upload-field';
import InputField from '@app/views/molecules/responder-form-fields/input-field';
import LinearRatingField from '@app/views/molecules/responder-form-fields/linear-rating';
import MultipleChoiceField from '@app/views/molecules/responder-form-fields/multiple-choice-field';
import MultipleChoiceWithMultipleSelection from '@app/views/molecules/responder-form-fields/multiple-choice-with-multiple-selections';
import PhoneNumberField from '@app/views/molecules/responder-form-fields/phone-number-field';
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

// A #rrggbb page colour at ~90% opacity; anything else (unset, named colours)
// falls back to a translucent white.
function headerGround(accent?: string) {
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
            if (field?.properties?.allowMultipleSelection) {
                return <MultipleChoiceWithMultipleSelection field={field} slideIndex={slideIndex} />;
            }
            return <MultipleChoiceField field={field} slideIndex={slideIndex} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} />;
        case FieldTypes.FILE_UPLOAD:
            return <FileUploadField field={field} />;
        case FieldTypes.DROP_DOWN:
            return <DropDownField field={field} slideIndex={slideIndex} />;
        case FieldTypes.PHONE_NUMBER:
            return <PhoneNumberField field={field} />;
        case FieldTypes.RATING:
            return <RatingField field={field} />;
        case FieldTypes.DATE:
            return <DateField field={field} />;
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
    const formSlideFromState = standardForm.fields[index];
    const formSlide = formSlideData ? formSlideData : formSlideFromState;

    const { currentSlide, setCurrentSlideToThankyouPage, nextSlide, goToSlide, previousSlide, setResponderState, responderState, setCurrentSlideToWelcomePage } = useResponderState();

    const { formResponse, setInvalidFields, setFormResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    // Calculated fields follow the answers live (logic, jumps and piping read them).
    useCalculatedFields(standardForm?.fields);
    const workspace = useAppSelector(selectWorkspace);
    const [submitResponse, { isLoading }] = useSubmitResponseMutation();
    const { files } = useFormAtom();
    const authState = useAppSelector(selectAuth);

    // Identity sharing is opt-in (DESIGN.md §5 — "leave consent unchecked;
    // the person opts in"): until the responder touches the checkbox, a logged-in
    // responder on an identity-optional form stays anonymous. Forms that require
    // a verified identity keep it attached, as they state up front.
    const identityOptional = !!authState.id && !standardForm?.settings?.requireVerifiedIdentity;
    const effectiveAnonymize = formResponse.anonymize ?? identityOptional;

    const submitFormResponse = async () => {
        const formData = new FormData();

        const postBody = {
            form_id: standardForm?.formId,
            // Repeating groups the responder saw carry at least their minimum items.
            // ...and groups hidden by logic or off the visited path are dropped.
            answers: normalizeGroupAnswersForSubmit(standardForm?.fields, formResponse.answers ?? {}, [...(responderState.history || []), currentSlide]),
            // Hidden-field (URL parameter) values captured when the form loaded.
            ...(Object.keys(hiddenValues).length ? { hidden_fields: hiddenValues } : {}),
            anonymize: effectiveAnonymize,
            form_version: standardForm?.version || 1
        };

        formData.append('response', JSON.stringify(postBody));
        // The date calculations used (today()); the server takes it when it is plausible.
        formData.append('today', localToday());
        const aiNoticeToken = aiNoticeTokenToSend(standardForm);
        if (aiNoticeToken) formData.append('ai_notice_token', aiNoticeToken);
        files.forEach((fileObj) => {
            formData.append('files', fileObj.file, fileObj.fileName);
            formData.append('file_field_ids', fileObj.fieldId);
            formData.append('file_ids', fileObj.fileId);
        });
        const response: any = await submitResponse({
            workspaceId: workspace.id,
            formId: standardForm?.formId,
            body: formData
        });
        if (!response.data) {
            const failure: Error & { response?: unknown } = new Error('The response was not accepted.');
            failure.response = response?.error;
            throw failure;
        }
        // Reflect what was actually submitted, so the thank-you page reports
        // the anonymity state truthfully.
        if (formResponse.anonymize === undefined) {
            setFormResponse({ ...formResponse, anonymize: effectiveAnonymize });
        }
        return response.data;
    };

    // Fields hidden by conditional logic given the answers so far. Recomputed each
    // render, so the form reacts live as the responder answers earlier questions.
    const hiddenFieldIds = getHiddenFieldIds(formSlide?.properties?.fields, formResponse.answers || {});
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
    const endsHere = currentSlide === index && resolveJump(formSlide, formResponse.answers || {})?.target === JUMP_TARGET_SUBMIT;
    const submitsHere = isLastPage || endsHere;
    // A failed submission, shown by the button until the next attempt.
    const [submitError, setSubmitError] = useState(false);

    const [sendFlowEvent] = useSendFlowEventMutation();
    // Anonymous drop-off breadcrumb: page → page, never answers, never in preview.
    const emitFlow = (fromPage: string, toPage: string) => {
        if (isPreviewMode || !workspace?.id || !standardForm?.formId) return;
        sendFlowEvent({ workspaceId: workspace.id, formId: standardForm.formId, sessionId: getFlowSessionId(standardForm.formId), fromPage, toPage }).catch(() => {});
    };

    // Submit, then show the ending the deciding jump named (`endingId`), or
    // the default ending. Respondents never see an ending without submitting.
    const finishForm = (endingId?: string) => {
        if (isPreviewMode) setCurrentSlideToThankyouPage(endingId);
        else
            submitFormResponse()
                .then((responderId) => {
                    setResponderState({
                        ...responderState,
                        currentSlide: -2,
                        responderId,
                        endingId
                    });
                })
                .catch((e) => {
                    if (!showServerAnswerErrors(e?.response)) {
                        toast({ description: t('NAV.SUBMIT_ERROR'), variant: 'destructive' });
                        setSubmitError(true);
                    }
                });
    };

    // The server refused some answers (422 invalid_answers): put its problems
    // on the questions and go back to the first page that has one.
    const showServerAnswerErrors = (error: unknown): boolean => {
        const errors = serverAnswerErrors(error);
        if (!errors) return false;
        const slides = standardForm?.fields ?? [];
        const invalid = serverInvalidations(slides, errors);
        setInvalidFields(invalid);
        toast({ description: t('NAV.SUBMIT_INVALID'), variant: 'destructive' });
        const page = firstPageWithError(slides, errors);
        if (page >= 0 && page !== currentSlide) {
            setResponderState({ ...responderState, currentSlide: page, currentField: 0, prevActiveField: -1, prevActiveSlide: currentSlide, history: historyBackTo(responderState.history, currentSlide, page) });
        }
        const firstKey = Object.keys(invalid)[0];
        // after the page change has rendered; as onNext does
        if (firstKey)
            setTimeout(() => {
                if (parseScopedFieldId(firstKey)) document.getElementById(firstKey)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
                else scrollToDivById(firstKey);
            }, 600);
        return true;
    };

    const onNext = () => {
        setSubmitError(false);
        // Only validate fields the responder can actually see.
        const visibleSlide = { ...formSlide, properties: { ...formSlide?.properties, fields: (formSlide?.properties?.fields || []).filter((f: StandardFormFieldDto) => !hiddenFieldIds.has(f.id)) } };
        const invalidations = {
            ...validateSlide(visibleSlide as StandardFormFieldDto, formResponse.answers || {}),
            // Repeating groups: item limits, and required questions per item
            // (keyed by the item-scoped id the question renders under).
            ...validateGroupsInSlide(visibleSlide.properties.fields, formResponse.answers || {})
        };
        // Answer rules (length, format, value range, number of options) on
        // answers given; a missing one is Required's to report.
        Object.entries(validateAnswerRulesInSlide(visibleSlide.properties.fields, formResponse.answers || {})).forEach(([id, problems]) => {
            if (!invalidations[id]) invalidations[id] = problems as any;
        });
        // Date rules (e.g. "after Start date"), on top of a missing answer.
        Object.entries(validateDateRulesInSlide(visibleSlide.properties.fields, formResponse.answers || {}, getInputFieldsById(standardForm?.fields))).forEach(([id, problems]) => {
            invalidations[id] = [...(invalidations[id] ?? []), ...problems] as any;
        });
        setInvalidFields(invalidations);
        if (Object.keys(invalidations).length !== 0) {
            // Every key is the id of the element to bring into view; questions
            // inside a group item sit in nested containers, so let the browser
            // find their scroll position.
            const firstKey = Object.keys(invalidations)[0];
            if (parseScopedFieldId(firstKey)) document.getElementById(firstKey)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
            else scrollToDivById(firstKey);
            return;
        }

        // Page-jump / branching: a matching rule overrides the linear next page.
        const jump = resolveJump(formSlide, formResponse.answers || {});
        const jumpTargetId = jump?.target || null;
        if (jumpTargetId === JUMP_TARGET_SUBMIT) {
            if (isPreviewMode) toast({ description: 'Logic rule matched → submitting the form' });
            emitFlow(formSlide.id, '__submit__');
            finishForm(jump?.endingId || undefined);
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
            emitFlow(formSlide.id, '__submit__');
            finishForm();
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
                {/* The bar sits over the scrolling questions: give it the page's
                    ground (translucent + blur, so it also works over gradient or image
                    backgrounds) or questions scroll through the header text. */}
                <div
                    className={cn('backdrop-blur-sm absolute top-0 right-0 left-0 z-10 mx-auto w-full', leaflet ? 'flex h-14 items-center border-b' : 'pt-5 pb-3')}
                    style={{
                        background: headerGround(formSlide?.properties?.theme?.accent || standardForm?.theme?.accent),
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
                                {(workspace?.title || workspace?.workspaceName) && (
                                    <span className="hidden items-center gap-1.5 rounded-full border border-black-400 bg-white/85 px-2.5 py-0.5 font-medium text-black-800 sm:inline-flex">
                                        <Shield className="h-3.5 w-3.5 text-brand-500" strokeWidth={1.8} aria-hidden="true" />
                                        {workspace?.title || workspace?.workspaceName}
                                    </span>
                                )}
                                <span className="font-medium whitespace-nowrap tabular-nums" lang={language}>
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
                        {pageFields.map((field: StandardFormFieldDto, position: number) => (
                            // 12-grid width on desktop: adjacent spans that fit pack
                            // into one row (two 6s sit side by side); mobile stays a
                            // flex column, where the span style is inert.
                            <div key={field.id} className={cn('min-w-0', fieldSpacingClass(field, position === pageFields.length - 1))} style={{ gridColumn: `span ${clampSpan(field)} / span ${clampSpan(field)}` }}>
                                <FormFieldComponent field={field} slideIndex={formSlide!.index} />
                            </div>
                        ))}
                    </QuestionNumberContext.Provider>
                    {/* The button belongs to the last answer: 32px above it,
                        a little closer than the 48px between questions. */}
                    <div
                        // Leaflet: the button lines up with the question text, past the margin column.
                        className={cn('-mt-4 flex flex-col items-start gap-4', leaflet && 'ml-[var(--leaflet-margin,34px)]', leaflet && numbering?.hang && '@min-[880px]/page:ml-0')}
                        style={{ gridColumn: 'span 12 / span 12' }}
                    >
                        {submitsHere && (
                            <>
                                {authState.id && !standardForm.settings?.requireVerifiedIdentity && (
                                    // Consent gets a calm, legible home of its own (DESIGN.md §2/§4):
                                    // 15px/1.5, high contrast, green-tinted container — and unchecked by
                                    // default, so sharing identity is a choice the person makes.
                                    // Named by the consent statement; the hint (whose email) describes it.
                                    <label className="flex w-fit max-w-[560px] cursor-pointer flex-row items-start gap-3 rounded-[8px] border border-[#BFE0D2] bg-[#F2FAF6] p-4">
                                        {/* A real checkbox, not the text-field component: that one paints a
                                            solid white background, which hid the tick when checked. */}
                                        <input
                                            checked={!effectiveAnonymize}
                                            onChange={(e) => {
                                                setFormResponse({
                                                    ...formResponse,
                                                    anonymize: !e.target.checked
                                                });
                                            }}
                                            type="checkbox"
                                            aria-labelledby="share-email-consent-label"
                                            aria-describedby="share-email-consent-hint"
                                            data-testid="share-email-consent"
                                            className="mt-0.5 h-5 w-5 shrink-0 cursor-pointer rounded-[4px] border-2 border-control text-[#0E8A5F] checked:border-[#0E8A5F]"
                                        />
                                        <span className="flex flex-col gap-0.5">
                                            <span id="share-email-consent-label" className="text-[15px] leading-relaxed font-medium text-black-900">
                                                {t('CONSENT.SHARE_EMAIL')}
                                            </span>
                                            <span id="share-email-consent-hint" className="text-[13px] text-black-700">
                                                {t('CONSENT.SHARE_EMAIL_HINT', { email: authState?.email })}
                                            </span>
                                        </span>
                                    </label>
                                )}
                            </>
                        )}
                        <Button
                            flat
                            // Filled with the action colour unless the theme's button style says otherwise (theme-root.ts).
                            style={formButtonStyle(standardForm.theme?.secondary, leaflet ? '4px' : '8px')}
                            isLoading={isLoading}
                            className={cn('form-button min-h-12 px-8 py-3 text-base font-semibold', leaflet ? 'rounded-[4px]' : 'rounded-[8px]')}
                            onClick={onNext}
                            size="medium"
                        >
                            {submitsHere ? t('NAV.SUBMIT') : t('NAV.CONTINUE')}
                        </Button>
                        {/* Stays until the next attempt; the toast alone is gone in a moment. */}
                        {submitError && (
                            <p role="alert" className="text-[15px] leading-relaxed font-medium text-[#B42318]" lang={language}>
                                {t('NAV.SUBMIT_ERROR')}
                            </p>
                        )}
                    </div>
                </div>
            </SlideLayoutWrapper>
        </Controller>
    );
}
