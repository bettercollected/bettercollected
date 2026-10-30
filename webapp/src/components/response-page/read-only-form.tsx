'use client';

import { CSSProperties } from 'react';

import { formContentLanguage } from '@app/lib/hooks/use-form-content-language';
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isShownToRespondents } from '@app/utils/calculated-fields';
import { logicSourcesById } from '@app/utils/conditional-logic';
import { downloadFile } from '@app/utils/file-utils';
import { resolveFormLogo } from '@app/utils/form-logo';
import { pageSectionTitle, questionNumbers } from '@app/utils/leaflet-sections';
import { hasSeveralPages, plainQuestionNumbers } from '@app/utils/question-numbering';
import { fieldHasAnswer, formFormatLanguage, responsePageSections, themeWithDefaults } from '@app/utils/response-page';
import FormLogoStrip from '@app/views/molecules/form/form-logo-strip';
import { themeRootProps } from '@app/views/molecules/theme/theme-root';
import { leafletColours, softInk, styleTokens, themeBackgroundStyle } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, FORM_GUTTER, clampSpan, fieldSpacingClass } from '@app/views/organism/layout/form-column';

import { ANSWERED_THEN_SKIPPED, NotShownQuestion, ReadOnlyContext, ReadOnlyQuestion, isContent, pageQuestions } from './read-only-question';

/** The "Error downloading file" path: the server's signed link, fetched and saved, as everywhere else. */
function useDownload() {
    const { toast } = useToast();
    return async (file: { url?: string; name?: string; id?: string }) => {
        try {
            if (!file.url) return;
            await downloadFile(file.url, file.name ?? file.id ?? 'file');
        } catch {
            toast({ description: 'Error downloading file', variant: 'destructive' });
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
    const workspace = useAppSelector(selectWorkspace);
    const onDownload = useDownload();
    const theme = themeWithDefaults(form.theme);
    const tokens = styleTokens(theme.style);
    const answers = response.answers ?? {};
    const unreadable = (response.unreadableFields ?? []).includes('answers');
    const root = themeRootProps(theme);
    const logo = resolveFormLogo(form, workspace);
    const sections = responsePageSections(form, answers);
    const slides = form.fields ?? [];
    const leaflet = tokens.key === 'leaflet';
    const several = hasSeveralPages(slides);
    const sources = logicSourcesById(slides);
    const hiddenFields = response.hiddenFields ?? {};
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
        pipe: { slides, answers, hiddenValues: hiddenFields },
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
            <main className={cn(FORM_GUTTER, 'py-10 lg:py-14')} aria-label="Response">
                <div className={cn(FORM_COLUMN, 'mx-auto flex flex-col gap-14')} lang={lang}>
                    <h1 className="form-title-face text-[28px] leading-tight font-bold" style={{ color: theme.primary }}>
                        {form.title?.trim() || 'Untitled form'}
                    </h1>
                    {sections.map(({ page, number, visited }) => {
                        // staff-only (internal) fields are the team's, shown in their own panel below, never in the form's look
                        const fields = ((page.properties?.fields ?? []) as StandardFormFieldDto[]).filter((field) => !field.internal);
                        // unreadable answers say nothing about what the rules showed or skipped: every question is listed
                        const rows = unreadable ? fields.map((field) => ({ field, notShown: false })) : pageQuestions(fields, answers, sources);
                        // the numbers the respondent saw: only what the form showed them
                        const shown = rows.filter((row) => !row.notShown && isShownToRespondents(row.field)).map((row) => row.field);
                        const numbers = leaflet ? questionNumbers(shown, number) : page.properties?.showQuestionNumbers ? plainQuestionNumbers(shown, number, several) : undefined;
                        const ctx = { ...baseContext, numbers };
                        const headingId = `rp-page-${page.id}`;
                        const title = pageSectionTitle(page);
                        return (
                            <section key={page.id} aria-labelledby={headingId} data-page={number} className="flex flex-col gap-8">
                                <h2 id={headingId} className={cn('border-b pb-2 text-[13px] font-medium tabular-nums', sections.length === 1 && 'sr-only')} style={{ color: softInk(theme), borderColor: leafletColours(theme).rule }}>
                                    {`Page ${number} of ${sections.length}`}
                                    {title ? ` · ${title}` : ''}
                                </h2>
                                {!visited && !unreadable ? (
                                    <SkippedPage fields={fields} answers={answers} ctx={ctx} />
                                ) : (
                                    <div className="flex flex-col gap-12 lg:grid lg:grid-cols-12 lg:gap-x-6">
                                        {rows.map(({ field, notShown }, position) => (
                                            <div key={field.id} className={cn('min-w-0', fieldSpacingClass(field, position === rows.length - 1))} style={{ gridColumn: `span ${clampSpan(field)} / span ${clampSpan(field)}` }}>
                                                {notShown ? <NotShownQuestion field={field} ctx={ctx} idPrefix="rp-" /> : <ReadOnlyQuestion field={field} answers={answers} ctx={ctx} />}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </section>
                        );
                    })}
                    {Object.keys(hiddenFields).length > 0 && (
                        <section aria-labelledby="rp-hidden-fields" className="flex flex-col gap-3 border-t pt-6" style={{ borderColor: leafletColours(theme).rule }}>
                            <h2 id="rp-hidden-fields" className="text-[13px] font-medium" style={{ color: softInk(theme) }}>
                                Hidden fields (from the share link)
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
 * A page the respondent's answers sent them past: said once, its questions
 * kept in a collapsed list. An answer given on it before the respondent went
 * back and changed course is still stored (and in the table and the export):
 * it is shown, marked "Answered, then skipped", and the list opens for it.
 */
function SkippedPage({ fields, answers, ctx }: { fields: StandardFormFieldDto[]; answers: Record<string, any>; ctx: ReadOnlyContext }) {
    const questions = fields.filter((field) => !isContent(field));
    const answeredCount = questions.filter((field) => fieldHasAnswer(field, answers)).length;
    const summary = `Show the ${questions.length} ${questions.length === 1 ? 'question' : 'questions'} on this page` + (answeredCount > 0 ? ` (${answeredCount} answered)` : '');
    return (
        <div className="flex flex-col gap-3" data-page-skipped>
            <p className="text-[15px] italic" style={{ color: softInk(ctx.theme) }}>
                {answeredCount > 0
                    ? 'Skipped: this respondent\'s answers sent them past this page. Answers given here before they changed course are still stored, and shown below.'
                    : 'Skipped: this respondent\'s answers sent them past this page.'}
            </p>
            {questions.length > 0 && (
                <details className="text-[15px]" open={answeredCount > 0}>
                    <summary className="cursor-pointer font-medium" style={{ color: softInk(ctx.theme) }}>
                        {summary}
                    </summary>
                    <div className="mt-4 flex flex-col gap-6">
                        {questions.map((field) =>
                            fieldHasAnswer(field, answers) ? (
                                <ReadOnlyQuestion key={field.id} field={field} answers={answers} ctx={ctx} note={field.type === FieldTypes.CALCULATED ? 'Calculated, on a page the respondent skipped' : ANSWERED_THEN_SKIPPED} />
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
