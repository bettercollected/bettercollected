import parse from 'html-react-parser';

import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { resolvePipesInText, resolvePipesInTitle } from '@app/utils/answer-piping';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import { RenderImage } from '@app/views/organism/form-builder/fields/render-field';
import { getPlaceholderValueForTitle } from '../rich-text-editor';

export default function QuestionWrapper({ field, children }: { field: StandardFormFieldDto; children?: React.ReactNode }) {
    const { formResponse } = useFormResponse();
    const { theme } = useFormState();
    const tokens = styleTokens(theme?.style);
    const { hiddenValues } = useHiddenFieldValues();
    const standardForm = useAppSelector(selectForm);

    const { invalidFields } = formResponse;
    const hasError = !!(invalidFields && invalidFields[field.id] && invalidFields[field.id].length);

    // A field that collects an answer is either required or optional — never
    // ambiguous. We mark required fields (asterisk) AND label optional ones, so
    // no one is nudged into answering something they could skip. Display-only
    // fields (statements, images) collect nothing, so they carry no marker.
    // (Design-Language.md §5: "Don't hide which fields are optional to coerce answers".)
    const isAnswerable = field?.type ? V2InputFields.includes(field.type) : false;
    const isRequired = !!field?.validations?.required;

    // Quiet ordinal for answerable questions ("01" meta label, Design-Language
    // §2). Numbering encodes a real sequence, and it's the structural anchor
    // that makes the generous question spacing read composed rather than empty.
    // Counted among answerable siblings on the same page, so statements and
    // media don't consume numbers; restarts per page, matching page context.
    const questionNumber = (() => {
        if (!isAnswerable) return null;
        for (const slide of standardForm?.fields ?? []) {
            const siblings = slide?.properties?.fields ?? [];
            const position = siblings.findIndex((sibling) => sibling.id === field.id);
            if (position >= 0) {
                return siblings.slice(0, position).filter((sibling) => sibling.type && V2InputFields.includes(sibling.type)).length + 1;
            }
        }
        return null;
    })();

    // Answer piping: swap pipe tokens for the responder's earlier answers (or
    // captured hidden-field values) before the title/description hit the DOM.
    const pipeContext = { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues };
    const resolvedTitle = resolvePipesInTitle(field?.title, pipeContext);
    const resolvedDescription = resolvePipesInText(field?.description, pipeContext);

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
                      'aria-describedby': [resolvedDescription ? `q-desc-${field.id}` : null, hasError ? `q-error-${field.id}` : null].filter(Boolean).join(' ') || undefined
                  }
                : {})}
        >
            <div className="relative">
                {/* Studio: an oversized ghost numeral behind the block. */}
                {questionNumber !== null && tokens.ordinal === 'ghost' && (
                    <span aria-hidden="true" className="pointer-events-none absolute -left-2 -top-7 hidden select-none text-[72px] font-extrabold leading-none lg:block" style={{ color: (theme?.secondary ?? '#2456CC') + '17' }}>
                        {String(questionNumber).padStart(2, '0')}
                    </span>
                )}
                <div className="relative flex flex-wrap items-baseline gap-x-2.5">
                    {/* The ordinal is the accent: a small mono number in the theme's
                        action colour on the label's own baseline (classic), a pale
                        serif numeral in the margin register (sheet), or the ghost
                        numeral above (studio). Numbers encode a real sequence — the
                        page's rhythm marker. Labels: weight and contrast carry the
                        hierarchy, not size (ratified 2026-07-08 against the mocks). */}
                    {questionNumber !== null && tokens.ordinal === 'inline' && (
                        <span aria-hidden="true" style={{ color: theme?.secondary }} className="font-mono text-[13px] font-medium tabular-nums">
                            {String(questionNumber).padStart(2, '0')}
                        </span>
                    )}
                    {questionNumber !== null && tokens.ordinal === 'gutter' && (
                        <span aria-hidden="true" style={{ color: (theme?.primary ?? '#101826') + '4D' }} className="font-serif text-[15px] tabular-nums">
                            {String(questionNumber).padStart(2, '0')}
                        </span>
                    )}
                    <div id={`q-title-${field.id}`} className={`${tokens.labelClass} [&_p]:inline`}>
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
            </div>
            <RenderImage field={field} />
            {children}
            {/* Honest, non-alarmist validation: say what to do, not just that something is wrong,
                and avoid alarm colours/urgency (Design-Language.md §5). */}
            {hasError && (
                <div id={`q-error-${field.id}`} role="alert" className="mt-2 text-sm text-amber-700">
                    Please answer this question to continue.
                </div>
            )}
        </div>
    );
}
