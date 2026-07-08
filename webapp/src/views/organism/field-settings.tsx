'use client';

import { useEffect, useState } from 'react';

import globalConstants from '@app/constants/global';
import { FieldTypes } from '@app/models/dtos/form';
import { Switch } from '@app/shadcn/components/ui/switch';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useActiveFieldComponent } from '@app/store/jotai/active-builder-component';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { formFieldsList } from '@app/constants/form-fields';
import FieldConditionalLogicEditor from '@app/views/molecules/form-builder/field-conditional-logic';

export default function FieldSettings() {
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { updateFieldRequired, activeSlide, activeField, updateDescription, updateFieldProperty, updateFieldColSpan, updateRatingSteps, updateFieldImage, updateAllowMultipleSelectionMatrixField } = useFormFieldsAtom();

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
            updateRatingSteps(activeSlide!.index, activeField!.index, e.target.value, activeField?.type);
        }
        setStepValue(e.target.value);
    };

    const NonImageFieldType = [FieldTypes.TEXT, null, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT];

    function getImageValue(checked: boolean): string {
        if (checked) {
            return activeField?.imageUrl ? activeField!.imageUrl : globalConstants.defaultFieldImage;
        } else return '';
    }

    return (
        <div className="flex flex-col gap-4 px-4 py-6">
            {/* The drawer replaces the Page/Design tabs while a field is
                selected — give people an explicit way back (Esc also works). */}
            <button type="button" onClick={() => setActiveFieldComponent(null)} className="text-black-600 hover:text-black-900 -mb-1 flex w-fit items-center gap-1 text-xs font-medium">
                ‹ Back to page
            </button>
            <div className="flex flex-col gap-1.5">
                <div className="text-black-800 truncate text-sm font-semibold" title={activeField ? extractTextfromJSON(activeField) : ''}>
                    {activeField ? extractTextfromJSON(activeField) : ''}
                </div>
                {activeField?.type && (
                    <span className="bg-black-100 text-black-600 w-fit rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                        {formFieldsList.find((f) => f.type === activeField.type)?.name ?? activeField.type.replaceAll('_', ' ').toLowerCase()}
                    </span>
                )}
            </div>
            <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Settings</div>
            <div className="flex w-full flex-col gap-1.5">
                <div className="text-black-700 text-xs">Width</div>
                {/* 12-column grid: Full = 12, 1/2 = 6, … — adjacent fields whose
                    spans fit share a row on desktop; mobile always stacks. */}
                <div className="border-black-300 flex overflow-hidden rounded-md border" role="group" aria-label="Field width">
                    {(
                        [
                            { label: 'Full', span: 12 },
                            { label: '2/3', span: 8 },
                            { label: '1/2', span: 6 },
                            { label: '1/3', span: 4 },
                            { label: '1/4', span: 3 }
                        ] as const
                    ).map((option) => {
                        const current = Math.min(12, Math.max(1, activeField?.properties?.colSpan ?? 12));
                        const selected = current === option.span;
                        return (
                            <button
                                key={option.span}
                                type="button"
                                aria-pressed={selected}
                                onClick={() => updateFieldColSpan(activeField!.index, activeSlide!.index, option.span)}
                                className={`flex-1 px-1 py-1.5 text-[11px] font-medium transition-colors ${selected ? 'bg-brand-100 text-brand-600' : 'text-black-600 hover:bg-black-100 bg-white'}`}
                            >
                                {option.label}
                            </button>
                        );
                    })}
                </div>
                <p className="text-black-500 text-[11px] leading-relaxed">Fields that fit side by side share a row. Phones always stack.</p>
            </div>
            <div className="flex w-full items-center justify-between">
                <div className="text-black-700 text-xs">Description</div>
                <Switch
                    checked={activeField?.description !== undefined && activeField?.description !== null}
                    onCheckedChange={(checked) => {
                        updateDescription(activeField!.index, activeSlide!.index, checked ? '' : undefined);
                    }}
                />
            </div>
            {activeField?.type !== FieldTypes.TEXT && (
                <div className="flex w-full items-center justify-between">
                    <div className="text-black-700 text-xs mr-4">{activeField?.type === FieldTypes.MATRIX ? 'Require a response in each row' : 'Required'}</div>
                    <Switch
                        checked={activeField?.validations?.required || false}
                        onCheckedChange={(checked) => {
                            updateFieldRequired(activeField!.index, activeSlide!.index, checked);
                        }}
                    />
                </div>
            )}
            {!NonImageFieldType.includes(activeField?.type) && (
                <div className="flex w-full items-center justify-between">
                    <div className="text-black-700 text-xs">Field Image</div>
                    <Switch
                        checked={!!activeField?.imageUrl}
                        onCheckedChange={(checked) => {
                            updateFieldImage(getImageValue(checked));
                        }}
                    />
                </div>
            )}

            {(activeField?.type === FieldTypes.MULTIPLE_CHOICE || activeField?.type === FieldTypes.MATRIX) && (
                <>
                    {activeField?.type !== FieldTypes.MATRIX && (
                        <>
                            <div className="flex w-full items-center justify-between">
                                <div className="text-black-700 text-xs">&quot;Other&quot; Option</div>
                                <Switch
                                    checked={activeField?.properties?.allowOtherChoice || false}
                                    onCheckedChange={(checked) => {
                                        updateFieldProperty(activeField!.index, activeSlide!.index, 'allowOtherChoice', checked);
                                    }}
                                />
                            </div>
                        </>
                    )}

                    <div className="flex w-full items-center justify-between">
                        <div className="text-black-700 text-xs">Multiple Selection</div>
                        <Switch
                            checked={activeField?.properties?.allowMultipleSelection || false}
                            onCheckedChange={(checked) => {
                                if (activeField?.type === FieldTypes.MATRIX) {
                                    updateAllowMultipleSelectionMatrixField(checked);
                                } else {
                                    updateFieldProperty(activeField!.index, activeSlide!.index, 'allowMultipleSelection', checked);
                                }
                            }}
                        />
                    </div>
                </>
            )}
            {(activeField?.type === FieldTypes.LINEAR_RATING || activeField?.type === FieldTypes.RATING) && (
                <div className="flex flex-col gap-2">
                    <div className="flex flex-row items-center justify-between text-xs">
                        <span>Steps : </span>
                        <input
                            type="number"
                            // defaultValue={defaultValue}
                            value={stepValue}
                            onChange={(e) => handleStepsChange(e)}
                            placeholder="steps"
                            className="focus:border-black-900 h-8 w-14 rounded border p-0 px-2 text-center text-sm"
                        />
                    </div>
                    {errorMsg && <span className="text-xs text-red-500">{errorMsg}</span>}
                </div>
            )}

            <FieldConditionalLogicEditor />
        </div>
    );
}
