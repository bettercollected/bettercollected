'use client';

import { CSSProperties, Fragment, MouseEvent as ReactMouseEvent } from 'react';

import { useTranslation } from 'react-i18next';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { FormTheme } from '@app/constants/theme';

import { formContentLanguage } from '@app/lib/hooks/use-form-content-language';
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { contrast } from '@app/utils/color-contrast';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isShownToRespondents } from '@app/utils/calculated-fields';
import { runHeadings } from '@app/utils/layout-containers';
import { resolvePipesInTitle } from '@app/utils/answer-piping';
import { logicSourcesById } from '@app/utils/conditional-logic';
import { downloadFile } from '@app/utils/file-utils';
import { resolveFormLogo } from '@app/utils/form-logo';
import { leafletSection, questionNumbers } from '@app/utils/leaflet-sections';
import { hasSeveralPages, plainQuestionNumbers } from '@app/utils/question-numbering';
import { fieldHasAnswer, formFormatLanguage, responsePageSections, themeWithDefaults } from '@app/utils/response-page';
import FormLogoStrip from '@app/views/molecules/form/form-logo-strip';
import { themeRootProps } from '@app/views/molecules/theme/theme-root';
import { leafletColours, softInk, styleTokens, themeBackgroundStyle } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, FORM_GUTTER, clampSpan, fieldSpacingClass } from '@app/views/organism/layout/form-column';

import { ANSWERED_THEN_SKIPPED, CALCULATED_SKIPPED, NotShownQuestion, ReadOnlyContext, ReadOnlyQuestion, isContent, pageQuestions } from './read-only-question';

export const CONTENTS_ID = 'contents';
export const CONTENTS_HEADING_ID = 'rp-contents-heading';
const pageHeadingId = (number: number) => `rp-page-heading-${number}`;

/**
 * Following an in-page link (the contents list, the toolbar's "Contents"):
 * scroll to the target (its `scroll-margin-top` keeps it clear of the sticky
 * toolbar) and move focus to its heading, so the keyboard and a screen reader
 * carry on from there.
 *
 * Done here rather than by the browser: a plain `#hash` link adds a history
 * entry without the router's state, and the router ignores Back onto such an
 * entry, so after "Next response" the browser's Back would show the address
 * of one response and the page of another (and every contents click would
 * add a Back step). The address gets the hash in place, with the router's
 * state kept. A click that opens a new tab or window is left to the browser.
 */
export function followInPageLink(event: ReactMouseEvent<HTMLAnchorElement>, targetId: string, headingId: string) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    document.getElementById(targetId)?.scrollIntoView?.({ block: 'start' });
    try {
        window.history.replaceState(window.history.state, '', `#${targetId}`);
    } catch {
        // the address is a convenience; the scroll and focus are what matter
    }
    document.getElementById(headingId)?.focus({ preventScroll: true });
}

interface ContentsSection {
    number: number;
    title: string;
    shortTitle: string;
    skipped: boolean;
    skippedWithAnswers: boolean;
}

/**
 * The form's contents, as on the respondent's welcome page: every page's
 * number and name, each a link to its section here. A page the respondent
 * was sent past says so; one that still holds answers given before that says
 * so differently. Kept in print, as a table of contents.
 */
function ContentsList({ sections, theme, leaflet }: { sections: ContentsSection[]; theme: FormTheme; leaflet: boolean }) {
    const { t } = useTranslation();
    const rule = leafletColours(theme).rule;
    const numeralInk = theme.secondary && theme.accent && contrast(theme.secondary, theme.accent) >= 4.5 ? theme.secondary : theme.primary;
    return (
        <nav id={CONTENTS_ID} aria-labelledby={CONTENTS_HEADING_ID} className="scroll-mt-28" data-contents>
            <h2 id={CONTENTS_HEADING_ID} tabIndex={-1} className="text-[15px] font-semibold focus:outline-hidden" style={{ color: theme.primary }}>
                {t('RESPONSE_PAGE.CONTENTS')}
            </h2>
            <ol className="mt-2 border-t" style={{ borderColor: rule }}>
                {sections.map((section) => (
                    <li key={section.number} className="border-b" style={{ borderColor: rule }}>
                        <a
                            href={`#page-${section.number}`}
                            onClick={(event) => followInPageLink(event, `page-${section.number}`, pageHeadingId(section.number))}
                            className="grid grid-cols-[34px_minmax(0,1fr)_auto] items-baseline gap-x-2 rounded-sm py-2.5 text-base underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--focus-ring)"
                            style={{ color: theme.primary }}
                        >
                            <span className="tabular-nums" style={{ fontFamily: leaflet ? leafletSerif.style.fontFamily : undefined, fontWeight: 600, color: numeralInk }}>
                                <span className="sr-only">{t('RESPONSE_PAGE.PAGE_SR')}</span>{' '}
                                {section.number}
                            </span>{' '}
                            <span className="[overflow-wrap:anywhere]">
                                {!section.title ? (
                                    t('RESPONSE_PAGE.PAGE_N', { n: section.number })
                                ) : section.shortTitle && section.shortTitle !== section.title ? (
                                    <>
                                        <span aria-hidden="true">{section.shortTitle}</span>
                                        <span className="sr-only">{section.title}</span>
                                    </>
                                ) : (
                                    section.title
                                )}
                            </span>
                            {section.skipped && (
                                <>
                                    {' '}
                                    {section.skippedWithAnswers ? (
                                        <span className="rounded-full border px-2 py-0.5 text-[12px] font-medium whitespace-nowrap" style={{ borderColor: theme.tertiary, color: theme.primary }} data-skipped="with-answers">
                                            {t('RESPONSE_PAGE.SKIPPED_KEPT')}
                                        </span>
                                    ) : (
                                        <span className="text-[13px] whitespace-nowrap italic" style={{ color: softInk(theme) }} data-skipped="empty">
                                            {t('RESPONSE_PAGE.SKIPPED')}
                                        </span>
                                    )}
                                </>
                            )}
                        </a>
                    </li>
                ))}
            </ol>
        </nav>
    );
}

/** The "Error downloading file" path: the server's signed link, fetched and saved, as everywhere else. */
function useDownload() {
    const { toast } = useToast();
    const { t } = useTranslation();
    return async (file: { url?: string; name?: string; id?: string }) => {
        try {
            if (!file.url) return;
            await downloadFile(file.url, file.name ?? file.id ?? 'file');
        } catch {
            toast({ description: t('RESPONSE_PAGE.FILE_ERROR'), variant: 'destructive' });
        }
    };
}

/**
 * One response drawn like the form it was given on, read-only, on one page:
 * the form's theme (face, colours, background, corners, logo), each page of
 * the form a section, each question with its options or answer marked.
 *
 * Nothing here writes to the respondent's answer state: it takes the
 * response and the form (the version it was submitted against) as data.
 */
export default function ReadOnlyForm({ form, response }: { form: StandardFormDto; response: StandardFormResponseDto }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const onDownload = useDownload();
    const theme = themeWithDefaults(form.theme);
    const tokens = styleTokens(theme.style);
    const answers = response.answers ?? {};
    const unreadable = (response.unreadableFields ?? []).includes('answers');
    const root = themeRootProps(theme);
    const logo = resolveFormLogo(form, workspace);
    const slides = form.fields ?? [];
    const hiddenFields = response.hiddenFields ?? {};
    const pipe = { slides, answers, hiddenValues: hiddenFields };
    // Each page with the name the respondent's contents list gives it (its
    // section title, else its opening heading, else its first question), and
    // whether this respondent was sent past it (and left answers on it first).
    const sections = responsePageSections(form, answers).map((section) => {
        // staff-only (internal) fields are the team's, shown in their own panel below, never in the form's look
        const own = ((section.page.properties?.fields ?? []) as StandardFormFieldDto[]).filter((field) => !field.internal);
        // as on the respondent's page: an opening text block's pipes are resolved before its heading names the page
        const named = own.map((field, position) => (position === 0 && field.type === FieldTypes.TEXT ? ({ ...field, title: resolvePipesInTitle(field.title, pipe) } as StandardFormFieldDto) : field));
        const name = leafletSection(named, '', section.page.properties?.sectionTitle);
        // An opening heading that names the page is said once, in the page's
        // heading: the rest of that text block (if any) opens the page, as the
        // respondent's Leaflet page does with its intro band.
        const fields = name.openingTextId ? named.flatMap((field) => (field.id !== name.openingTextId ? [field] : name.intro ? [name.intro] : [])) : own;
        const skipped = !section.visited && !unreadable;
        return {
            ...section,
            fields,
            title: name.title,
            shortTitle: name.shortTitle,
            // Only a name the page gives itself (its section title or opening heading) goes into its heading. A name
            // taken from its first question is not repeated right above that question; the contents list keeps it.
            headingTitle: name.titleFromPage ? name.title : '',
            skipped,
            skippedWithAnswers: skipped && fields.some((field) => answeredBeforeSkipping(field, answers))
        };
    });
    const leaflet = tokens.key === 'leaflet';
    const several = hasSeveralPages(slides);
    const sources = logicSourcesById(slides);
    const lang = formContentLanguage(form.settings?.language, 'en');

    const vars = {
        ['--rp-edge' as string]: theme.tertiary,
        ['--rp-rule' as string]: leafletColours(theme).rule,
        ['--rp-field-radius' as string]: tokens.fieldRadius,
        ['--rp-card-radius' as string]: tokens.cardRadius,
        ['--focus-ring' as string]: theme.secondary
    };

    const baseContext: ReadOnlyContext = {
        form,
        theme,
        pipe,
        sources,
        unreadable,
        lang,
        formatLanguage: formFormatLanguage(form.settings?.language),
        onDownload
    };

    return (
        <div
            {...root.attributes}
            data-response-form
            // the form's own face, ground and ink; the ground fills the band, the column sits in it
            className="w-full font-form print:break-inside-auto"
            style={{ ...themeBackgroundStyle(theme), color: theme.primary, ...vars, ...root.style } as CSSProperties}
        >
            {logo && <FormLogoStrip logo={logo} theme={theme} />}
            <main className={cn(FORM_GUTTER, 'py-10 lg:py-14')} aria-label={t('RESPONSE_PAGE.FORM_LABEL')}>
                <div className={cn(FORM_COLUMN, 'mx-auto flex flex-col gap-14')} lang={lang}>
                    <h1 className="form-title-face text-[28px] leading-tight font-bold" style={{ color: theme.primary }}>
                        {form.title?.trim() || t('RESPONSE_PAGE.UNTITLED_FORM')}
                    </h1>
                    {sections.length > 1 && <ContentsList sections={sections} theme={theme} leaflet={leaflet} />}
                    {sections.map(({ page, number, fields, headingTitle, skipped }) => {
                        // unreadable answers say nothing about what the rules showed or skipped: every question is listed
                        const rows = unreadable ? fields.map((field) => ({ field, notShown: false })) : pageQuestions(fields, answers, sources);
                        // the numbers the respondent saw: only what the form showed them
                        const shown = rows.filter((row) => !row.notShown && isShownToRespondents(row.field)).map((row) => row.field);
                        const numbers = leaflet ? questionNumbers(shown, number) : page.properties?.showQuestionNumbers ? plainQuestionNumbers(shown, number, several) : undefined;
                        const ctx = { ...baseContext, numbers };
                        const headings = runHeadings(
                            page,
                            rows.map((row) => row.field.id)
                        );
                        const headingId = pageHeadingId(number);
                        return (
                            // `page-<n>`: the page's number only, never its title (it lands in the URL as the contents link's hash)
                            <section key={page.id} id={`page-${number}`} aria-labelledby={headingId} data-page={number} className="flex scroll-mt-28 flex-col gap-8">
                                <h2 id={headingId} tabIndex={-1} className={cn('border-b pb-2 text-[13px] font-medium tabular-nums focus:outline-hidden', sections.length === 1 && 'sr-only')} style={{ color: softInk(theme), borderColor: leafletColours(theme).rule }}>
                                    {t('RESPONSE_PAGE.PAGE_N_OF', { n: number, total: sections.length })}
                                    {headingTitle ? ` · ${headingTitle}` : ''}
                                </h2>
                                {skipped ? (
                                    <SkippedPage fields={fields} answers={answers} ctx={ctx} />
                                ) : (
                                    <div className="flex flex-col gap-12 lg:grid lg:grid-cols-12 lg:gap-x-6">
                                        {rows.map(({ field, notShown }, position) => (
                                            <Fragment key={field.id}>
                                                {/* flat, in page order; a layout container's (or tab's) title heads its questions */}
                                                {headings[position] && (
                                                    <h3 className="text-[17px] leading-snug font-semibold [overflow-wrap:anywhere] lg:col-span-12" style={{ color: theme.primary }}>
                                                        {headings[position]}
                                                    </h3>
                                                )}
                                                <div className={cn('min-w-0', fieldSpacingClass(field, position === rows.length - 1))} style={{ gridColumn: `span ${clampSpan(field)} / span ${clampSpan(field)}` }}>
                                                    {notShown ? <NotShownQuestion field={field} ctx={ctx} idPrefix="rp-" /> : <ReadOnlyQuestion field={field} answers={answers} ctx={ctx} />}
                                                </div>
                                            </Fragment>
                                        ))}
                                    </div>
                                )}
                            </section>
                        );
                    })}
                    {Object.keys(hiddenFields).length > 0 && (
                        <section aria-labelledby="rp-hidden-fields" className="flex flex-col gap-3 border-t pt-6" style={{ borderColor: leafletColours(theme).rule }}>
                            <h2 id="rp-hidden-fields" className="text-[13px] font-medium" style={{ color: softInk(theme) }}>
                                {t('RESPONSE_PAGE.HIDDEN_FIELDS')}
                            </h2>
                            <dl className="flex flex-col gap-3">
                                {Object.entries(hiddenFields).map(([name, value]) => (
                                    <div key={name} className="flex flex-col gap-0.5">
                                        <dt className="font-mono text-[13px]" style={{ color: softInk(theme) }}>
                                            {name}
                                        </dt>
                                        <dd className="text-base [overflow-wrap:anywhere]">{value}</dd>
                                    </div>
                                ))}
                            </dl>
                        </section>
                    )}
                </div>
            </main>
        </div>
    );
}

/**
 * Whether a question on a skipped page holds an answer the respondent gave
 * before changing course. A calculated value never does: the server works out
 * and stores every calculation on every submission, whatever the path (a sum
 * of nothing is 0), so its value says nothing about a visit.
 */
function answeredBeforeSkipping(field: StandardFormFieldDto, answers: Record<string, any>): boolean {
    return !isContent(field) && field.type !== FieldTypes.CALCULATED && fieldHasAnswer(field, answers);
}

/**
 * A page the respondent's answers sent them past: said once, its questions
 * kept in a collapsed list. An answer given on it before the respondent went
 * back and changed course is still stored (and in the table and the export):
 * it is shown, marked "Answered, then skipped", and the list opens for it.
 * A calculated value is listed with its own note, but neither counts as an
 * answer nor opens the list (see answeredBeforeSkipping).
 */
function SkippedPage({ fields, answers, ctx }: { fields: StandardFormFieldDto[]; answers: Record<string, any>; ctx: ReadOnlyContext }) {
    const { t } = useTranslation();
    const questions = fields.filter((field) => !isContent(field));
    const answeredCount = questions.filter((field) => answeredBeforeSkipping(field, answers)).length;
    const summary = answeredCount > 0 ? t('RESPONSE_PAGE.SHOW_QUESTIONS_ANSWERED', { count: questions.length, answered: answeredCount }) : t('RESPONSE_PAGE.SHOW_QUESTIONS', { count: questions.length });
    return (
        <div className="flex flex-col gap-3" data-page-skipped>
            <p className="text-[15px] italic" style={{ color: softInk(ctx.theme) }}>
                {answeredCount > 0 ? t('RESPONSE_PAGE.SKIPPED_NOTE_KEPT') : t('RESPONSE_PAGE.SKIPPED_NOTE')}
            </p>
            {questions.length > 0 && (
                <details className="text-[15px]" open={answeredCount > 0}>
                    <summary className="cursor-pointer font-medium" style={{ color: softInk(ctx.theme) }}>
                        {summary}
                    </summary>
                    <div className="mt-4 flex flex-col gap-6">
                        {questions.map((field) =>
                            fieldHasAnswer(field, answers) ? (
                                <ReadOnlyQuestion key={field.id} field={field} answers={answers} ctx={ctx} note={field.type === FieldTypes.CALCULATED ? CALCULATED_SKIPPED : ANSWERED_THEN_SKIPPED} />
                            ) : (
                                <NotShownQuestion key={field.id} field={field} ctx={ctx} idPrefix="rp-" />
                            )
                        )}
                    </div>
                </details>
            )}
        </div>
    );
}
