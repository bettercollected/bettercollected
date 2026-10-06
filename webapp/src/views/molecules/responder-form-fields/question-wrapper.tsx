import parse from 'html-react-parser';

import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { resolvePipesInText, resolvePipesInTitle, stringTitleToDoc } from '@app/utils/answer-piping';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import { RenderImage } from '@app/views/organism/form-builder/fields/render-field';
import { getPlaceholderValueForTitle } from '../rich-text-editor';
import { HEADING_CLASSES } from '@app/utils/text-headings';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';

// Answer fields that V2InputFields (used elsewhere) leaves out; without them
// these never showed their "Optional" marker.
const ALSO_ANSWERABLE = [FieldTypes.LONG_TEXT, FieldTypes.LINK, FieldTypes.FILE_UPLOAD];

export default function QuestionWrapper({ field, children, errorMessage }: { field: StandardFormFieldDto; children?: React.ReactNode; errorMessage?: string }) {
    const { formResponse } = useFormResponse();
    const { theme } = useFormState();
    const tokens = styleTokens(theme?.style);
    const { hiddenValues } = useHiddenFieldValues();
    const standardForm = useAppSelector(selectForm);

    const { invalidFields } = formResponse;
    // A caller may own the error (e.g. a repeating group's item-count message).
    const hasError = errorMessage !== undefined ? !!errorMessage : !!(invalidFields && invalidFields[field.id] && invalidFields[field.id].length);

    // A field that collects an answer is either required or optional — never
    // ambiguous. We mark required fields (asterisk) AND label optional ones, so
    // no one is nudged into answering something they could skip. Display-only
    // fields (statements, images) collect nothing, so they carry no marker.
    // (Design-Language.md §5: "Don't hide which fields are optional to coerce answers".)
    const isAnswerable = field?.type ? V2InputFields.includes(field.type) || ALSO_ANSWERABLE.includes(field.type) : false;
    const isRequired = !!field?.validations?.required;

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
    const { t, language } = useRespondentLanguage();
    const whyWeAsk = field?.properties?.whyWeAsk?.trim();

    return (
        <div
            className={`relative flex flex-col gap-1 lg:gap-2 ${tokens.divider ? 'border-b pb-7' : ''}`}
            style={tokens.divider ? { borderColor: (theme?.tertiary ?? '#818CA0') + '40' } : undefined}
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
            <div className="relative">
                <div className="relative flex flex-wrap items-baseline gap-x-2.5">
                    {/* Labels: weight and contrast carry the hierarchy, not size
                        (ratified 2026-07-08 against the form-redesign mocks). */}
                    <div id={`q-title-${field.id}`} className={`${tokens.labelClass} [&_p]:inline ${HEADING_CLASSES}`}>
                        {parse(getHtmlFromJson(resolvedTitle) ?? getPlaceholderValueForTitle(field?.type || FieldTypes.TEXT))}
                        {isAnswerable && isRequired && (
                            <>
                                <span aria-hidden="true" className="text-[#C43D3D]">
                                    {' '}
                                    *
                                </span>
                                <span className="sr-only"> (required)</span>
                            </>
                        )}
                    </div>
                    {isAnswerable && !isRequired && <span className="text-black-700 text-xs font-normal tracking-wide">Optional</span>}
                </div>
                {resolvedDescription && (
                    <div id={`q-desc-${field.id}`} className="text-black-700 mt-1.5 max-w-[62ch] text-[15px] leading-relaxed">
                        {resolvedDescription}
                    </div>
                )}
                {whyWeAsk && (
                    <p id={`q-why-${field.id}`} className="text-black-700 border-brand-200 mt-1.5 max-w-[62ch] border-l-2 pl-2.5 text-[14px] leading-relaxed">
                        <span className="text-black-800 font-semibold" lang={language}>
                            {t('QUESTION.WHY_WE_ASK')}
                        </span>{' '}
                        {whyWeAsk}
                    </p>
                )}
            </div>
            <RenderImage field={field} />
            {children}
            {/* Honest, non-alarmist validation: say what to do, not just that something is wrong,
                and avoid alarm colours/urgency (Design-Language.md §5). */}
            {hasError && (
                <div id={`q-error-${field.id}`} role="alert" className="mt-2 text-sm text-amber-700">
                    {errorMessage || 'Please answer this question to continue.'}
                </div>
            )}
        </div>
    );
}
