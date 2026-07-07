import parse from 'html-react-parser';

import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { resolvePipesInText, resolvePipesInTitle } from '@app/utils/answer-piping';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import RequiredIcon from '@Components/icons/required';

import { RenderImage } from '@app/views/organism/form-builder/fields/render-field';
import { getPlaceholderValueForTitle } from '../rich-text-editor';

export default function QuestionWrapper({ field, children }: { field: StandardFormFieldDto; children?: React.ReactNode }) {
    const { formResponse } = useFormResponse();
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

    // Answer piping: swap pipe tokens for the responder's earlier answers (or
    // captured hidden-field values) before the title/description hit the DOM.
    const pipeContext = { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues };
    const resolvedTitle = resolvePipesInTitle(field?.title, pipeContext);
    const resolvedDescription = resolvePipesInText(field?.description, pipeContext);

    return (
        <div className="relative flex flex-col gap-1 lg:gap-2" id={field.id}>
            {isRequired && (
                <div className="absolute -right-2 top-2">
                    <RequiredIcon className="text-black-900" />
                </div>
            )}
            <div className="">
                <div className="flex flex-wrap items-baseline gap-x-2">
                    {/* The question owns the screen: 24px/600 ink (Design-Language §2) —
                        bigger and darker than anything else, including the answer. */}
                    <div className="text-xl font-semibold leading-snug lg:text-2xl">{parse(getHtmlFromJson(resolvedTitle) ?? getPlaceholderValueForTitle(field?.type || FieldTypes.TEXT))}</div>
                    {isAnswerable && !isRequired && <span className="text-black-700 text-xs font-normal tracking-wide">Optional</span>}
                </div>
                {resolvedDescription && <div className="text-black-700 mt-1.5 max-w-[62ch] text-[15px] leading-relaxed">{resolvedDescription}</div>}
            </div>
            <RenderImage field={field} />
            {children}
            {/* Honest, non-alarmist validation: say what to do, not just that something is wrong,
                and avoid alarm colours/urgency (Design-Language.md §5). */}
            {hasError && <div className="mt-2 text-sm text-amber-700">Please answer this question to continue.</div>}
        </div>
    );
}
