import { useContext, useEffect, useRef } from 'react';

import parse from 'html-react-parser';
import { AlertCircle } from 'lucide-react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { resolvePipesInText, resolvePipesInTitle, stringTitleToDoc } from '@app/utils/answer-piping';
import { answerRuleMessage, checkAnswerRules, isAnswerRuleProblem } from '@app/utils/answer-rules';
import { isAnswerableField } from '@app/utils/leaflet-sections';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { HEADING_CLASSES, TEXT_BLOCK_BODY_CLASSES } from '@app/utils/text-headings';
import { contrast, invalidEdge, requiredMarkColour, softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';
import { RenderImage } from '@app/views/organism/form-builder/fields/render-field';

import { getPlaceholderValueForTitle } from '../rich-text-editor';
import { QuestionNumberContext } from './question-number-context';

export default function QuestionWrapper({ field, children, errorMessage }: { field: StandardFormFieldDto; children?: React.ReactNode; errorMessage?: string }) {
    const { formResponse } = useFormResponse();
    const { theme } = useFormState();
    const tokens = styleTokens(theme?.style);
    const { hiddenValues } = useHiddenFieldValues();
    const standardForm = useAppSelector(selectForm);

    const { invalidFields } = formResponse;
    const { t, language } = useRespondentLanguage();
    // Answer rules (length, format, range, number of options): flagged on
    // Continue, then re-checked against the answer as it is now, so the
    // message goes away as soon as the answer is fixed.
    const flagged = invalidFields?.[field.id] ?? [];
    const flaggedOnlyRules = flagged.length > 0 && flagged.every(isAnswerRuleProblem);
    const ruleProblems = flaggedOnlyRules ? checkAnswerRules(field, formResponse.answers?.[field.id]) : [];
    const ruleMessage = ruleProblems.length ? answerRuleMessage(field, ruleProblems[0], t) : undefined;
    // A caller may own the error (e.g. a repeating group's item-count message).
    const hasError = errorMessage !== undefined ? !!errorMessage : flaggedOnlyRules ? !!ruleMessage : flagged.length > 0;

    // A field that collects an answer is either required or optional — never
    // ambiguous. We mark required fields (asterisk) AND label optional ones, so
    // no one is nudged into answering something they could skip. Display-only
    // fields (statements, images) collect nothing, so they carry no marker.
    // (DESIGN.md §5: "Don't hide which fields are optional to coerce answers".)
    const isAnswerable = isAnswerableField(field);
    const isRequired = !!field?.validations?.required;
    // A text block is content, not a question: it reads as body text (its
    // own headings keep their sizes), not in the question-label style.
    const isTextBlock = field?.type === FieldTypes.TEXT;

    // Answer piping: swap pipe tokens for the responder's earlier answers (or
    // captured hidden-field values) before the title/description hit the DOM.
    const pipeContext = { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues };
    // Plain-string titles (groups, AI/MCP-created fields) go through the TipTap
    // path as text nodes — never as raw HTML — so neither the title nor a piped
    // answer or URL prefill can inject markup. Bold keeps the string path's look.
    const title = typeof field?.title === 'string' && field.title ? stringTitleToDoc(field.title, [{ type: 'bold' }]) : field?.title;
    const resolvedTitle = resolvePipesInTitle(title, pipeContext);
    const resolvedDescription = resolvePipesInText(field?.description, pipeContext);
    // "Why we ask this": the creator's reason for an identifying question.
    const whyWeAsk = field?.properties?.whyWeAsk?.trim();
    // Leaflet: the question's n.m number, set in the margin column.
    const numbering = useContext(QuestionNumberContext);
    const number = numbering?.numbers[field.id];
    const leaflet = tokens.key === 'leaflet';
    // Numerals wear the action colour where it reads as text on the page, else the ink.
    const numberColour = theme?.secondary && theme?.accent && contrast(theme.secondary, theme.accent) >= 4.5 ? theme.secondary : theme?.primary;

    // While the error shows, the field's own controls say so too: they are
    // marked invalid and described by the message (the inputs are rendered
    // by each field type, so they are reached here rather than threaded
    // through every component), and their edge turns signal red.
    const groupRef = useRef<HTMLDivElement>(null);
    const errorId = `q-error-${field.id}`;
    useEffect(() => {
        const controls = groupRef.current?.querySelectorAll<HTMLElement>('input:not([type=hidden]), textarea, select, [role=radiogroup], [role=combobox]');
        controls?.forEach((control) => {
            // Only this question's own controls, not those of nested questions.
            if (control.closest('[data-question-wrapper]') !== groupRef.current) return;
            const describedBy = (control.getAttribute('aria-describedby') ?? '').split(' ').filter((id) => id && id !== errorId);
            if (hasError) {
                control.setAttribute('aria-invalid', 'true');
                control.setAttribute('aria-describedby', [...describedBy, errorId].join(' '));
            } else {
                control.removeAttribute('aria-invalid');
                if (describedBy.length) control.setAttribute('aria-describedby', describedBy.join(' '));
                else control.removeAttribute('aria-describedby');
            }
        });
    });

    const content = (
        <>
            <div className="relative">
                <div className="relative flex flex-wrap items-baseline gap-x-2.5">
                    {/* Labels: weight and contrast carry the hierarchy, not size
                        (ratified 2026-07-08 against the form-redesign mocks). */}
                    <div id={`q-title-${field.id}`} className={`${isTextBlock ? TEXT_BLOCK_BODY_CLASSES : `${tokens.labelClass} [&_p]:inline`} ${HEADING_CLASSES}`} style={{ color: theme?.primary }}>
                        {parse(getHtmlFromJson(resolvedTitle) ?? getPlaceholderValueForTitle(field?.type || FieldTypes.TEXT))}
                        {isAnswerable && isRequired && (
                            <>
                                <span aria-hidden="true" style={{ color: requiredMarkColour(theme) }}>
                                    {' '}
                                    *
                                </span>
                                <span className="sr-only"> {t('FIELD.REQUIRED')}</span>
                            </>
                        )}
                    </div>
                    {isAnswerable && !isRequired && <span className="text-[13px] font-normal text-black-700">{t('FIELD.OPTIONAL')}</span>}
                </div>
                {resolvedDescription && (
                    <div id={`q-desc-${field.id}`} className="mt-1.5 max-w-[62ch] text-[15px] leading-relaxed text-black-700">
                        {resolvedDescription}
                    </div>
                )}
                {whyWeAsk && (
                    // The reason sits against a rule in the theme's border colour
                    // (Leaflet: a 3px margin-note rule in the action colour), so
                    // it belongs to the form's palette, not the app's blue.
                    <p
                        id={`q-why-${field.id}`}
                        className={cn('mt-2 max-w-[62ch] text-[14px]', leaflet ? 'border-l-[3px] pl-2.5 leading-normal' : 'border-l-2 pl-3 leading-relaxed text-black-700')}
                        style={leaflet ? { borderColor: theme?.secondary, color: softInk(theme) } : { borderColor: theme?.tertiary ?? '#818CA0' }}
                    >
                        <span className="font-semibold" style={{ color: theme?.primary }} lang={language}>
                            {t('QUESTION.WHY_WE_ASK')}
                        </span>{' '}
                        {whyWeAsk}
                    </p>
                )}
            </div>
            <RenderImage field={field} />
            {children}
            {/* Honest, non-alarmist validation: say what to do, not just that something is wrong,
                and avoid alarm colours/urgency (DESIGN.md §5). The message is set in the
                theme's ink (amber text fell under 4.5:1 on the tinted presets); the icon in
                danger red marks it as a problem without relying on the colour of the words. */}
            {hasError && (
                <div id={errorId} role="alert" className="mt-2 flex items-start gap-2 text-[15px] leading-snug font-medium" style={{ color: theme?.primary }}>
                    <AlertCircle className="mt-px h-[18px] w-[18px] shrink-0 text-[#C43D3D]" strokeWidth={2} aria-hidden="true" />
                    <span>{errorMessage || ruleMessage || t('FIELD.ANSWER_REQUIRED')}</span>
                </div>
            )}
        </>
    );

    return (
        <div
            className={cn(
                'relative',
                number ? 'grid grid-cols-[var(--leaflet-margin,34px)_minmax(0,1fr)] items-baseline' : 'flex flex-col gap-1 lg:gap-2',
                // Wide centred pages hang the number outside the text measure.
                number && numbering?.hang && '@min-[880px]/page:block',
                tokens.divider && 'border-b pb-7',
                // The field's edge (inputs, the date and dropdown triggers, the
                // option controls) in signal red while its error shows.
                hasError &&
                    '[&_[aria-expanded]]:border-(--invalid-edge)! [&_[aria-haspopup]]:border-(--invalid-edge)! [&_[data-choice-indicator]]:border-(--invalid-edge)! [&_input:not([type=checkbox])]:border-(--invalid-edge)! [&_textarea]:border-(--invalid-edge)!'
            )}
            style={{
                ...(tokens.divider ? { borderColor: (theme?.tertiary ?? '#818CA0') + '40' } : {}),
                ...(hasError ? { ['--invalid-edge' as string]: invalidEdge(theme) } : {})
            }}
            ref={groupRef}
            data-question-wrapper
            data-invalid={hasError || undefined}
            id={field.id}
            // Give assistive tech an accessible name/description for the field.
            // Answerable fields become a labelled group so the question (and any
            // description / validation message) is announced with the control.
            {...(isAnswerable
                ? {
                      role: 'group',
                      'aria-labelledby': `q-title-${field.id}`,
                      'aria-describedby': [resolvedDescription ? `q-desc-${field.id}` : null, whyWeAsk ? `q-why-${field.id}` : null, hasError ? `q-error-${field.id}` : null].filter(Boolean).join(' ') || undefined
                  }
                : {})}
        >
            {number ? (
                <>
                    {/* The number is a reading aid; the group's name is the question. */}
                    <span
                        aria-hidden="true"
                        data-testid="question-number"
                        className={cn('text-[16px] leading-[1.4] tabular-nums', numbering?.hang && '@min-[880px]/page:absolute @min-[880px]/page:top-0 @min-[880px]/page:-left-16 @min-[880px]/page:w-12 @min-[880px]/page:text-right')}
                        style={{ fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: numberColour }}
                    >
                        {number}
                    </span>
                    <div className="flex min-w-0 flex-col gap-1 lg:gap-2">{content}</div>
                </>
            ) : (
                content
            )}
        </div>
    );
}
