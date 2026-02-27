import React, { useState} from 'react';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import TabularInputField from './TabularInputField';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { FieldTypes } from '@app/models/dtos/form';

export default function TabularInputFieldBuilderWrapper({ field, slide }: { field: any, slide?: number }) {
    const { theme } = useFormState();
    const { addTabularRow, addTabularColumn, activeField, updateTabularInputValue } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const [isEditable, setIsEditable] = useState(true);

    const rowTitles = field?.properties?.rowTitles || [];
    const columnTitles = field?.properties?.columnTitles || [];
    const value = field?.properties?.value || [];

    return (
        <div className="flex flex-col gap-4">
            <div style={{ color: theme?.secondary }} className={cn('flex w-full justify-end', field.id !== activeField?.id && 'invisible')}>
                <span
                    className="cursor-pointer"
                    onClick={() => {
                        addTabularColumn();
                    }}
                >
                    Add Column
                </span>
            </div>
            <TabularInputField
                value={value}
                onChange={(val) => updateTabularInputValue(slide ?? -1, field.id, val)}
                rowTitles={rowTitles}
                columnTitles={columnTitles}
                disabled={isEditable}
            />
            <div style={{ color: theme?.secondary }} className={cn('text-brand-500 flex w-full justify-start', field.id !== activeField?.id && 'invisible')}>
                <span
                    className="cursor-pointer"
                    onClick={() => {
                        addTabularRow();
                    }}
                >
                    Add Row
                </span>
            </div>
        </div>
    );
}