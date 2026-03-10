import { useState} from 'react';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import TabularInputField from './TabularInputField';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { FieldTypes } from '@app/models/dtos/form';
import { StandardFormFieldDto } from '@app/models/dtos/form';

export default function TabularInputFieldBuilderWrapper({ field, slide }: { field: StandardFormFieldDto, slide?: number }) {
    const { theme } = useFormState();
    const { addTabularRow, addTabularColumn, activeField, updateTabularInputValue, deleteTabularRow, deleteTabularColumn } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();

    const rowTitles = field?.properties?.rowTitles || [];
    const columnTitles = field?.properties?.columnTitles || [];
    const value = field?.properties?.tabular_value || [];

    const slideIndex = slide !== undefined && slide >= 0 ? slide : activeSlideComponent?.index ?? 0;

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
                onChange={(val) => updateTabularInputValue(slideIndex, field.index, val)}
                rowTitles={rowTitles}
                columnTitles={columnTitles}
                disabled
                field={field}
                onDeleteRow={(rowIndex) => deleteTabularRow(slideIndex, field.index, rowIndex)}
                onDeleteColumn={(colIndex) => deleteTabularColumn(slideIndex, field.index, colIndex)}
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