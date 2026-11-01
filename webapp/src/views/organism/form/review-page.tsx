'use client';

import { useMemo } from 'react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { useDerivedAnswers } from '@app/lib/hooks/use-derived-answers';
import { statesFor } from '@app/lib/hooks/use-field-rule-states';
import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import { useOptionStates } from '@app/lib/hooks/use-option-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import SaveDraftControl from '@app/components/drafts/save-draft-control';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { pageInvalidations } from '@app/utils/page-validation';
import { AlsoSentRow, ReviewQuestion, ReviewRow, ReviewSection, alsoSentRows, pathPages, reviewProblems, reviewSections } from '@app/utils/review-page';
import useFocusProblem from './focus-problem';
import { actionText } from '@app/utils/theme-contrast';
import BackButton from '@app/views/molecules/form-builder/back-button';
import { formButtonStyle } from '@app/views/molecules/theme/theme-root';
import { mixHex, softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, columnPlacementClass } from '@app/views/organism/layout/form-column';

import ShareIdentityConsent from './share-identity-consent';
import { submitErrorKey, useEmitFlow, useFinishForm } from './use-finish-form';

const isHex = (value?: string) => !!value && /^#[0-9a-fA-F]{6}$/.test(value);

/**
 * The review page: after the last page, when the form asks for one, the
 * respondent reads their answers, page by page, and sends them from here.
 *
 * It is drawn from the answers in the browser, along the pages the
 * respondent went through (utils/review-page.ts): nothing has been sent or
 * stored yet, and the page says so. "Edit" returns to a page and "Back to
 * review" (on that page) returns here. Submitting uses the same path as the
 * last page's button, with the same refusals (form closed, not open yet,
 * full) kept by the button and the answers kept in the browser.
 */
export default function ReviewPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { t, language } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const standardForm = useAppSelector(selectResponderForm);
    const focusProblem = useFocusProblem();
    const { responderState, previousSlide, editFromReview } = useResponderState();
    const { formResponse, setInvalidFields } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const { finishForm, isLoading, submitError, setSubmitError, effectiveAnonymize } = useFinishForm(isPreviewMode);
    const emitFlow = useEmitFlow(isPreviewMode);
    const { files } = useFormAtom();
    // Calculations and values the rules set follow the path as it stands now (an edit may have
    // shortened it since the page they were last worked out on).
    useDerivedAnswers(standardForm?.fields, standardForm?.hiddenFields);
    const theme = standardForm?.theme;
    const leaflet = styleTokens(theme?.style).key === 'leaflet';
    const ink = theme?.primary;
    const quiet = softInk(theme);
    const edge = isHex(theme?.tertiary) && isHex(theme?.accent) ? mixHex(theme!.tertiary, theme!.accent, 0.45) : '#D0D5DD';
    const corner = leaflet ? '4px' : '8px';
    const serif = leaflet ? { fontFamily: leafletSerif.style.fontFamily } : undefined;

    const optionStates = useOptionStates();
    const path = useMemo(() => pathPages(responderState.history), [responderState.history]);
    const { sections, alsoSent } = useMemo(() => {
        const answers = formResponse.answers ?? {};
        // visited: the pages gone through (the review itself is not one)
        const states = statesFor(standardForm?.fields, answers, hiddenValues, standardForm?.hiddenFields, [...path, responderState.currentSlide]);
        const input = { slides: standardForm?.fields, answers, path, states, hiddenValues, language: (language === 'nl' ? 'nl' : 'en') as 'en' | 'nl', t };
        const sections = reviewSections(input);
        return { sections, alsoSent: alsoSentRows({ ...input, sections, files }) };
    }, [standardForm?.fields, standardForm?.hiddenFields, formResponse.answers, hiddenValues, path, responderState.currentSlide, language, t, files]);
    const problems = useMemo(() => reviewProblems(sections), [sections]);
    // The values the link carried (declared hidden fields): sent with every response.
    const linkValues = useMemo(() => Object.entries(hiddenValues ?? {}), [hiddenValues]);

    // To a page that needs something, with what it lacks marked, and the first such question in focus.
    const goFix = (slideIndex: number, key?: string) => {
        const answers = formResponse.answers ?? {};
        const states = statesFor(standardForm?.fields, answers, hiddenValues, standardForm?.hiddenFields, [...path, responderState.currentSlide]);
        const invalid = pageInvalidations(standardForm?.fields?.[slideIndex], standardForm?.fields, answers, states, undefined, optionStates);
        editFromReview(slideIndex);
        setInvalidFields(invalid);
        const target = key ?? Object.keys(invalid)[0];
        // after the page has changed, as a page's own validation does
        if (target)
            setTimeout(() => focusProblem(standardForm?.fields?.[slideIndex], target), 600);
    };

    const onSubmit = () => {
        setSubmitError(false);
        // Never possible after the pages' own checks, but the answers may have changed under them
        // (a rule now requiring an answer): the page that needs it, not a refusal from the server.
        if (problems.length) {
            goFix(problems[0].slideIndex, problems[0].row.key);
            return;
        }
        const last = path.length ? standardForm?.fields?.[path[path.length - 1]] : undefined;
        if (last) emitFlow(last.id, '__submit__');
        finishForm(responderState.reviewEndingId);
    };

    return (
        <div className={cn(FORM_COLUMN, columnPlacementClass(undefined), 'flex flex-col pb-10')} data-testid="review-column" lang={language}>
            <BackButton label={t('NAV.BACK')} handleClick={previousSlide} className="mt-5 mb-3 -ml-1.5 min-h-11 w-fit bg-inherit!" style={{ color: ink }} />
            <h1 data-page-start tabIndex={-1} className="max-w-[24ch] text-[28px] leading-[36px] font-bold tracking-[-0.02em] text-balance outline-none sm:text-[34px] sm:leading-[42px]" style={{ color: ink, ...serif }}>
                {t('REVIEW.TITLE')}
            </h1>
            <p className="mt-3 max-w-[60ch] text-[17px] leading-relaxed text-pretty" style={{ color: quiet }}>
                {sections.length ? t('REVIEW.INTRO') : t('REVIEW.EMPTY')}
            </p>
            {problems.length > 0 && (
                <p role="status" className="mt-4 max-w-[60ch] text-[15px] leading-relaxed font-medium text-[#B42318]">
                    {t('REVIEW.PROBLEMS', { count: problems.length })}
                </p>
            )}
            <div className="mt-8 flex flex-col gap-10">
                {sections.map((section) => (
                    <ReviewSectionView
                        key={section.slideIndex}
                        section={section}
                        ink={ink}
                        quiet={quiet}
                        edge={edge}
                        serif={serif}
                        link={actionText(theme)}
                        contentLang={contentLang}
                        onEdit={() => editFromReview(section.slideIndex)}
                        onFix={(key) => goFix(section.slideIndex, key)}
                    />
                ))}
            </div>
            {(alsoSent.length > 0 || linkValues.length > 0) && <AlsoSentView rows={alsoSent} linkValues={linkValues} ink={ink} quiet={quiet} edge={edge} serif={serif} contentLang={contentLang} />}
            <div className="mt-10 flex flex-col items-start gap-4">
                <ShareIdentityConsent effectiveAnonymize={effectiveAnonymize} />
                <Button flat style={formButtonStyle(theme?.secondary, corner)} isLoading={isLoading} className={cn('form-button min-h-12 px-8 py-3 text-base font-semibold', leaflet ? 'rounded-[4px]' : 'rounded-[8px]')} onClick={onSubmit} size="medium">
                    {t('NAV.SUBMIT')}
                </Button>
                {/* "Save and continue later" works from here too: the draft comes back on the last page, to go on to this review again. */}
                {!isPreviewMode && <SaveDraftControl ink={ink} />}
                {/* Stays until the next attempt; the toast alone is gone in a moment. */}
                {submitError && (
                    <p role="alert" className="text-[15px] leading-relaxed font-medium text-[#B42318]">
                        {t(submitErrorKey(submitError))}
                    </p>
                )}
            </div>
        </div>
    );
}

function ReviewSectionView({
    section,
    ink,
    quiet,
    edge,
    serif,
    link,
    contentLang,
    onEdit,
    onFix
}: {
    section: ReviewSection;
    ink?: string;
    quiet: string;
    edge: string;
    serif?: React.CSSProperties;
    link: string;
    contentLang: string | undefined;
    onEdit: () => void;
    onFix: (key: string) => void;
}) {
    const { t } = useRespondentLanguage();
    const headingId = `review-page-${section.slideIndex}`;
    const name = section.title ? t('REVIEW.PAGE_NAMED', { n: section.number, title: section.title }) : t('REVIEW.PAGE', { n: section.number });
    return (
        <section aria-labelledby={headingId} data-testid={`review-section-${section.slideIndex}`}>
            <div className="flex items-baseline justify-between gap-4 border-b pb-2" style={{ borderColor: edge }}>
                <h2 id={headingId} className="min-w-0 text-[19px] leading-snug font-semibold [overflow-wrap:anywhere]" style={{ color: ink, ...serif }}>
                    <span lang={section.title ? contentLang : undefined}>{name}</span>
                </h2>
                <button type="button" onClick={onEdit} className="min-h-11 shrink-0 cursor-pointer px-1 text-[15px] font-medium underline underline-offset-2" style={{ color: link }}>
                    {t('REVIEW.EDIT')} <span className="sr-only">{name}</span>
                </button>
            </div>
            {/* flat, in page order; a layout container's (or tab's) title heads its questions */}
            {runsOf(section.questions).map((run) => (
                <div key={run.questions[0].key}>
                    {run.heading && (
                        <h3 className="mt-5 text-[16px] leading-snug font-semibold [overflow-wrap:anywhere]" style={{ color: ink, ...serif }} lang={contentLang}>
                            {run.heading}
                        </h3>
                    )}
                    <dl className="flex flex-col">
                        {run.questions.map((question) => (
                            <QuestionView key={question.key} question={question} ink={ink} quiet={quiet} edge={edge} link={link} contentLang={contentLang} onFix={onFix} />
                        ))}
                    </dl>
                </div>
            ))}
        </section>
    );
}

/** The section's questions in runs: a run starts where a layout container's (or tab's) title heads questions, or where they stop being under one. */
function runsOf(questions: ReviewQuestion[]): Array<{ heading?: string | null; questions: ReviewQuestion[] }> {
    const runs: Array<{ heading?: string | null; questions: ReviewQuestion[] }> = [];
    for (const question of questions) {
        if (!runs.length || question.heading !== undefined) runs.push({ heading: question.heading, questions: [question] });
        else runs[runs.length - 1].questions.push(question);
    }
    return runs;
}

const PROBLEM_INK = '#B42318';

function QuestionView({ question, ink, quiet, edge, link, contentLang, onFix }: { question: ReviewQuestion; ink?: string; quiet: string; edge: string; link: string; contentLang: string | undefined; onFix: (key: string) => void }) {
    const { t } = useRespondentLanguage();
    if (!question.items) return <RowView row={question} ink={ink} quiet={quiet} edge={edge} link={link} contentLang={contentLang} onFix={onFix} />;
    return (
        <div className="border-b py-4" style={{ borderColor: edge }}>
            <dt className="text-[15px] leading-snug font-semibold [overflow-wrap:anywhere]" style={{ color: ink }} lang={contentLang}>
                {question.title}
            </dt>
            <dd className="mt-2 flex flex-col gap-4">
                {question.items.length === 0 && (
                    <span className="text-[16px] italic" style={{ color: quiet }}>
                        {t('REVIEW.NO_ENTRIES')}
                    </span>
                )}
                {question.items.map((item) => (
                    <div key={item.key} role="group" aria-label={item.header} className="rounded-[8px] border p-4" style={{ borderColor: edge }} data-testid="review-item">
                        <p className="text-[15px] leading-snug font-semibold [overflow-wrap:anywhere]" style={{ color: ink }}>
                            {item.header}
                        </p>
                        <dl className="mt-1 flex flex-col">
                            {item.rows.map((row) => (
                                <RowView key={row.key} row={row} ink={ink} quiet={quiet} edge={edge} link={link} contentLang={contentLang} onFix={onFix} last />
                            ))}
                        </dl>
                    </div>
                ))}
                {question.problem && (
                    <button type="button" onClick={() => onFix(question.key)} className="min-h-11 w-fit cursor-pointer text-left text-[15px] font-medium underline underline-offset-2" style={{ color: PROBLEM_INK }}>
                        {t('REVIEW.FIX')} <span className="sr-only">{question.title}</span>
                    </button>
                )}
            </dd>
        </div>
    );
}

function RowView({ row, ink, quiet, edge, link, contentLang, onFix, last = false }: { row: ReviewRow; ink?: string; quiet: string; edge: string; link: string; contentLang: string | undefined; onFix: (key: string) => void; last?: boolean }) {
    const { t } = useRespondentLanguage();
    return (
        <div className={cn(last ? 'py-3' : 'py-4', !last && 'border-b')} style={{ borderColor: edge }} data-testid="review-row">
            <dt className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[15px] leading-snug font-semibold [overflow-wrap:anywhere]" style={{ color: ink }}>
                <span lang={contentLang}>{row.title}</span>
                {row.locked && (
                    <span className="rounded-full border px-2 py-0.5 text-[12px] leading-snug font-medium" style={{ borderColor: edge, color: quiet }}>
                        {t(row.locked === 'filled' ? 'REVIEW.FILLED_IN' : 'FIELD.READ_ONLY')}
                    </span>
                )}
            </dt>
            <dd className="mt-1.5">
                {row.lines.length === 0 ? (
                    <span className="text-[16px] italic" style={{ color: row.problem ? PROBLEM_INK : quiet }}>
                        {t(row.problem === 'answer' ? 'REVIEW.NEEDS_ANSWER' : 'REVIEW.NOT_ANSWERED')}
                    </span>
                ) : row.lines.length === 1 ? (
                    // long text keeps its line breaks and wraps; a long word breaks rather than runs off the page
                    <span className="block text-[16px] leading-relaxed break-words whitespace-pre-wrap" style={{ color: ink }}>
                        {row.lines[0]}
                    </span>
                ) : (
                    <ul className="list-disc pl-5 text-[16px] leading-relaxed" style={{ color: ink }}>
                        {row.lines.map((line, index) => (
                            <li key={index} className="break-words whitespace-pre-wrap">
                                {line}
                            </li>
                        ))}
                    </ul>
                )}
                {row.problem && (
                    <button type="button" onClick={() => onFix(row.key)} className="mt-1 block min-h-11 cursor-pointer text-left text-[15px] font-medium underline underline-offset-2" style={{ color: row.problem === 'answer' ? PROBLEM_INK : link }}>
                        {t(row.problem === 'answer' ? 'REVIEW.ANSWER_IT' : 'REVIEW.FIX')} <span className="sr-only">{row.title}</span>
                    </button>
                )}
            </dd>
        </div>
    );
}

/**
 * What is sent although the review lists no question for it: earlier answers
 * to questions the form no longer shows, and uploaded files of such questions
 * or of pages that were skipped. Named, so that what the page says is what is sent.
 */
function AlsoSentView({ rows, linkValues, ink, quiet, edge, serif, contentLang }: { rows: AlsoSentRow[]; linkValues: Array<[string, string]>; ink?: string; quiet: string; edge: string; serif?: React.CSSProperties; contentLang: string | undefined }) {
    const { t } = useRespondentLanguage();
    return (
        <section aria-labelledby="review-also-sent" className="mt-10" data-testid="review-also-sent">
            <div className="border-b pb-2" style={{ borderColor: edge }}>
                <h2 id="review-also-sent" className="text-[19px] leading-snug font-semibold" style={{ color: ink, ...serif }}>
                    {t('REVIEW.ALSO_SENT')}
                </h2>
            </div>
            {rows.length > 0 && (
                <p className="mt-3 max-w-[60ch] text-[15px] leading-relaxed" style={{ color: quiet }}>
                    {t('REVIEW.ALSO_SENT_HINT')}
                </p>
            )}
            <dl className="flex flex-col">
                {rows.map((row) => (
                    <div key={row.key} className="border-b py-3" style={{ borderColor: edge }} data-testid="review-also-sent-row">
                        <dt className="text-[15px] leading-snug font-semibold [overflow-wrap:anywhere]" style={{ color: ink }}>
                            <span lang={contentLang}>{row.title}</span>
                            {row.page !== null && (
                                <span className="ml-3 text-[13px] font-normal" style={{ color: quiet }}>
                                    {t('REVIEW.PAGE', { n: row.page })}
                                </span>
                            )}
                        </dt>
                        <dd className="mt-1.5">
                            {row.lines.map((line, index) => (
                                <span key={index} className="block text-[16px] leading-relaxed break-words whitespace-pre-wrap" style={{ color: ink }}>
                                    {line}
                                </span>
                            ))}
                        </dd>
                    </div>
                ))}
            </dl>
            {/* The link's own values (the form's declared hidden fields) travel with every response. */}
            {linkValues.length > 0 && (
                <p className="mt-3 text-[15px] leading-relaxed break-words" style={{ color: ink }} data-testid="review-link-values">
                    <span className="font-semibold">{t('REVIEW.FROM_LINK')}</span> {linkValues.map(([name, value]) => `${name} = ${value}`).join(', ')}
                </p>
            )}
        </section>
    );
}
