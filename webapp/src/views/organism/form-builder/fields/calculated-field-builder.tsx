'use client';

import { Calculator, EyeOff } from 'lucide-react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useBuilderFieldsValue } from '@app/store/jotai/entity-hooks';
import { useFormState } from '@app/store/jotai/form';
import { calculationVariables, formulaText } from '@app/utils/calculated-fields';

/**
 * A calculated field on the canvas: its formula in readable form (field
 * references by label), edited in the inspector. Respondents see the value
 * here instead, unless it is hidden from them.
 */
export default function CalculatedFieldBuilder({ field }: { field: StandardFormFieldDto }) {
    const { formState } = useFormState();
    const expression = field.properties?.expression;
    const hiddenNames = formState.hiddenFields;
    // The formula names other questions by label: it follows them, and
    // re-renders this field only when the text shown changes.
    const formula = useBuilderFieldsValue((formFields) => formulaText(expression, calculationVariables(formFields, hiddenNames ?? [])), [expression, hiddenNames]);
    return (
        <div className="flex flex-col gap-1.5">
            <div className="flex items-start gap-3 rounded-lg border border-dashed border-black-400 bg-black-100 px-4 py-3">
                <Calculator className="mt-1 h-6 w-6 shrink-0 text-black-600" strokeWidth={1.75} aria-hidden="true" />
                {formula ? (
                    <code className="font-mono text-[22px] leading-snug break-all whitespace-pre-wrap text-black-800" aria-label={`Formula: ${formula}`}>
                        = {formula}
                    </code>
                ) : (
                    <span className="text-[22px] text-black-600">No formula yet. Write one in the inspector.</span>
                )}
            </div>
            {field.properties?.hiddenFromRespondents && (
                <span className="flex items-center gap-1.5 text-[20px] text-black-600">
                    <EyeOff className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" /> Hidden from respondents
                </span>
            )}
        </div>
    );
}
