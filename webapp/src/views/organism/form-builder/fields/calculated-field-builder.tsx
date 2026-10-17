'use client';

import { Calculator, EyeOff } from 'lucide-react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { calculationVariables, formulaText } from '@app/utils/calculated-fields';

/**
 * A calculated field on the canvas: its formula in readable form (field
 * references by label), edited in the inspector. Respondents see the value
 * here instead, unless it is hidden from them.
 */
export default function CalculatedFieldBuilder({ field }: { field: StandardFormFieldDto }) {
    const { formFields } = useFormFieldsAtom();
    const { formState } = useFormState();
    const formula = formulaText(field.properties?.expression, calculationVariables(formFields, formState.hiddenFields ?? []));
    return (
        <div className="flex flex-col gap-1.5">
            <div className="flex items-start gap-2 rounded-lg border border-dashed border-black-400 bg-black-100 px-3 py-2">
                <Calculator className="mt-0.5 h-4 w-4 shrink-0 text-black-600" strokeWidth={1.75} aria-hidden="true" />
                {formula ? (
                    <code className="font-mono text-xs break-all whitespace-pre-wrap text-black-800" aria-label={`Formula: ${formula}`}>
                        = {formula}
                    </code>
                ) : (
                    <span className="text-xs text-black-600">No formula yet. Write one in the inspector.</span>
                )}
            </div>
            {field.properties?.hiddenFromRespondents && (
                <span className="flex items-center gap-1 text-[11px] text-black-600">
                    <EyeOff className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" /> Hidden from respondents
                </span>
            )}
        </div>
    );
}
