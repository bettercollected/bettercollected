'use client';

import { FieldTypes } from '@app/models/dtos/form';
import { Switch } from '@app/shadcn/components/ui/switch';
import useFormBuilderAtom from '@app/store/jotai/fieldSelector';

export default function FieldSettings() {
    const {
        updateFieldRequired,
        activeSlide,
        activeField,
        updateDescription,
        updateFieldProperty
    } = useFormBuilderAtom();

    return (
        <div className="flex flex-col gap-4 px-4 py-6">
            <div className="p2-new !font-medium text-black-700">Settings</div>
            <div className="flex w-full items-center justify-between">
                <div className="text-xs text-black-700">Description</div>
                <Switch
                    checked={activeField?.description !== undefined}
                    onCheckedChange={(checked) => {
                        updateDescription(
                            activeField!.index,
                            activeSlide!.index,
                            checked ? '' : undefined
                        );
                    }}
                />
            </div>
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
            {activeField?.type === FieldTypes.MULTIPLE_CHOICE && (
                <>
                    <div className="flex w-full items-center justify-between">
                        <div className="text-xs text-black-700">
                            &quot;Other&quot; Option
                        </div>
                        <Switch
                            checked={activeField?.properties?.allowOtherOption || false}
                            onCheckedChange={(checked) => {
                                updateFieldProperty(
                                    activeField!.index,
                                    activeSlide!.index,
                                    'allowOtherOption',
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
        </div>
    );
}
