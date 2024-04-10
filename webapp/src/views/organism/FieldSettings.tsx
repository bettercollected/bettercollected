'use client';

import { useEffect, useState } from 'react';

import { FieldTypes } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { Switch } from '@app/shadcn/components/ui/switch';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';

export default function FieldSettings() {
    const {
        updateFieldRequired,
        activeSlide,
        activeField,
        updateDescription,
        updateFieldProperty,
        updateRatingSteps
    } = useFormFieldsAtom();

    const [errorMsg, setErrorMsg] = useState('');
    const [stepValue, setStepValue] = useState(activeField?.properties?.steps);

    useEffect(() => {
        setStepValue(activeField?.properties?.steps);
    }, [activeField?.properties?.steps]);

    const handleStepsChange = (e: any) => {
        setErrorMsg('');
        if (e.target.value <= 0 || e.target.value >= 50) {
            setErrorMsg('Value cant be less than 1 or greater than 50.');
        } else {
            updateRatingSteps(
                activeSlide!.index,
                activeField!.index,
                e.target.value,
                activeField?.type
            );
        }
        setStepValue(e.target.value);
    };

    return (
        <div className="flex flex-col gap-4 px-4 py-6">
            <div className="p2-new !font-medium text-black-700">Settings</div>
            <div className="flex w-full items-center justify-between">
                <div className="text-xs text-black-700">Description</div>
                <Switch
                    checked={
                        activeField?.description !== undefined &&
                        activeField?.description !== null
                    }
                    onCheckedChange={(checked) => {
                        updateDescription(
                            activeField!.index,
                            activeSlide!.index,
                            checked ? '' : undefined
                        );
                    }}
                />
            </div>
            {activeField?.type !== FieldTypes.TEXT && (
                <div className="flex w-full items-center justify-between">
                    <div className="text-xs text-black-700">Required</div>
                    <Switch
                        checked={activeField?.validations?.required || false}
                        onCheckedChange={(checked) => {
                            updateFieldRequired(
                                activeField!.index,
                                activeSlide!.index,
                                checked
                            );
                        }}
                    />
                </div>
            )}
            {activeField?.type === FieldTypes.MULTIPLE_CHOICE && (
                <>
                    <div className="flex w-full items-center justify-between">
                        <div className="text-xs text-black-700">
                            &quot;Other&quot; Option
                        </div>
                        <Switch
                            checked={activeField?.properties?.allowOtherChoice || false}
                            onCheckedChange={(checked) => {
                                updateFieldProperty(
                                    activeField!.index,
                                    activeSlide!.index,
                                    'allowOtherChoice',
                                    checked
                                );
                            }}
                        />
                    </div>
                    <div className="flex w-full items-center justify-between">
                        <div className="text-xs text-black-700">Multiple Selection</div>
                        <Switch
                            checked={
                                activeField?.properties?.allowMultipleSelection || false
                            }
                            onCheckedChange={(checked) => {
                                updateFieldProperty(
                                    activeField!.index,
                                    activeSlide!.index,
                                    'allowMultipleSelection',
                                    checked
                                );
                            }}
                        />
                    </div>
                </>
            )}
            {(activeField?.type === FieldTypes.LINEAR_RATING ||
                activeField?.type === FieldTypes.RATING) && (
                <div className="flex flex-col gap-2">
                    <div className="flex flex-row items-center justify-between text-xs">
                        <span>Steps : </span>
                        <input
                            type="number"
                            // defaultValue={defaultValue}
                            value={stepValue}
                            onChange={(e) => handleStepsChange(e)}
                            placeholder="steps"
                            className="h-8 w-14 rounded border p-0 px-2 text-center text-sm focus:border-black-900"
                        />
                    </div>
                    {errorMsg && (
                        <span className="text-xs text-red-500">{errorMsg}</span>
                    )}
                </div>
            )}
        </div>
    );
}
