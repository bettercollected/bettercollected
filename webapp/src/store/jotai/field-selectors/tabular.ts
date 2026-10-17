'use client';

import { v4 } from 'uuid';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import type { BuilderContext } from './index';

/** Table mutations of the builder: matrix rows and columns, and tabular input rows, columns and values. */
export function tabularMutators(ctx: BuilderContext) {
    const { formFields, setFormFields, activeSlideComponent, activeFieldComponent } = ctx;

    const updateRowTitle = (rowIndex: number, title: string) => {
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields![rowIndex]!.title = title;
        setFormFields([...formFields]);
    };

    const updateColumnTitle = (columnIndex: number, title: string) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields?.map((field) => {
            field.properties!.choices![columnIndex]!.value = title;
            return field;
        });
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = [...(updatedRows || [])];
        setFormFields([...formFields]);
    };

    const updateTabularRowTitle = (rowIdx: number, val: string) => {
        const slideIndex = activeSlideComponent!.index;
        const fieldIndex = activeFieldComponent!.index;
        const field = formFields[slideIndex]?.properties?.fields?.[fieldIndex];
        if (field?.properties?.rowTitles) {
            field.properties.rowTitles[rowIdx] = val;
            setFormFields([...formFields]);
        }
    };

    const updateTabularColumnTitle = (colIdx: number, val: string) => {
        const slideIndex = activeSlideComponent!.index;
        const fieldIndex = activeFieldComponent!.index;
        const field = formFields[slideIndex]?.properties?.fields?.[fieldIndex];
        if (field?.properties?.columnTitles) {
            field.properties.columnTitles[colIdx] = val;
            setFormFields([...formFields]);
        }
    };

    const addColumn = () => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields?.map((field) => {
            field.properties!.choices?.push({
                id: v4(),
                value: ''
            });
            return field;
        });
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = [...(updatedRows || [])];
        setFormFields([...formFields]);
    };

    const addRow = () => {
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields?.push({
            id: v4(),
            title: '',
            type: FieldTypes.MULTIPLE_CHOICE,
            index: formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.length + 1,
            properties: { ...formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields![0]!.properties }
        });
        setFormFields([...formFields]);
    };

    const deleteColumn = (columnIndex: number) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.map((field) => {
            const updatedChoices = field!.properties!.choices!.filter((choice, index) => index !== columnIndex);
            field!.properties!.choices = updatedChoices;
            return field;
        });

        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = updatedRows;
        setFormFields([...formFields]);
    };

    const updateAllowMultipleSelectionMatrixField = (allowMultipleSelectionMatrixField: boolean) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.map((field: StandardFormFieldDto) => {
            return {
                ...field,
                properties: {
                    ...(field?.properties || {}),
                    allowMultipleSelection: allowMultipleSelectionMatrixField
                }
            };
        });
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = updatedRows;
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties = {
            ...(formFields?.[activeSlideComponent!.index]?.properties?.fields?.[activeFieldComponent!.index]?.properties || {}),
            allowMultipleSelection: allowMultipleSelectionMatrixField
        };
        setFormFields([...formFields]);
    };

    const deleteRow = (rowIndex: number) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.filter((field, index) => index !== rowIndex);
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index].properties!.fields = updatedRows;
        setFormFields([...formFields]);
    };

    const updateTabularInputValue = (slideIndex: number, fieldIndex: number, value: string[][]) => {
        if (formFields[slideIndex] && formFields[slideIndex].properties && formFields[slideIndex].properties.fields && formFields[slideIndex].properties.fields[fieldIndex]) {
            formFields[slideIndex].properties.fields[fieldIndex].properties = {
                ...(formFields[slideIndex].properties.fields[fieldIndex].properties || {}),
                tabular_value: value
            };
            setFormFields([...formFields]);
        }
    };

    // Add a new row to the TabularInput field
    const addTabularRow = () => {
        const slideIndex = activeSlideComponent!.index;
        const fieldIndex = activeFieldComponent!.index;
        const field = formFields[slideIndex]?.properties?.fields?.[fieldIndex];
        if (!field?.properties) return;
        // Add a new row title
        field.properties.rowTitles = [...(field.properties.rowTitles || []), `Row ${(field.properties.rowTitles || []).length + 1}`];
        const colCount = field.properties.columnTitles?.length || 3;
        field.properties.tabular_value = [...(field.properties.tabular_value || []), Array(colCount).fill('')];
        setFormFields([...formFields]);
    };

    // Add a new column to the TabularInput field
    const addTabularColumn = () => {
        const slideIndex = activeSlideComponent!.index;
        const fieldIndex = activeFieldComponent!.index;
        const field = formFields[slideIndex]?.properties?.fields?.[fieldIndex];
        if (!field?.properties) return;
        // Add a new column title
        field.properties.columnTitles = [...(field.properties.columnTitles || []), `Col ${(field.properties.columnTitles || []).length + 1}`];
        field.properties.tabular_value = (field.properties.tabular_value || []).map((row) => [...row, '']);
        setFormFields([...formFields]);
    };

    // Delete a row from the TabularInput field
    const deleteTabularRow = (slideIndex: number, fieldIndex: number, rowIndex: number) => {
        const resolvedSlideIndex = slideIndex >= 0 ? slideIndex : activeSlideComponent!.index;
        const slide = formFields[resolvedSlideIndex];
        if (!slide?.properties?.fields) return;
        const field = slide.properties.fields[fieldIndex];
        if (!field?.properties) return;

        const currentRowTitles = field.properties?.rowTitles || [];
        const currentValue = field.properties?.tabular_value || [];

        field.properties = {
            ...(field.properties || {}),
            rowTitles: currentRowTitles.filter((_: any, i: number) => i !== rowIndex),
            tabular_value: currentValue.filter((_: any, i: number) => i !== rowIndex)
        };
        setFormFields([...formFields]);
    };

    const deleteTabularColumn = (slideIndex: number, fieldIndex: number, colIndex: number) => {
        const resolvedSlideIndex = slideIndex >= 0 ? slideIndex : activeSlideComponent!.index;
        const slide = formFields[resolvedSlideIndex];
        if (!slide?.properties?.fields) return;
        const field = slide.properties.fields[fieldIndex];
        if (!field?.properties) return;

        const currentColTitles = field.properties?.columnTitles || [];
        const currentValue = field.properties?.tabular_value || [];

        field.properties = {
            ...(field.properties || {}),
            columnTitles: currentColTitles.filter((_: any, i: number) => i !== colIndex),
            tabular_value: currentValue.map((row: string[]) => row.filter((_: string, i: number) => i !== colIndex))
        };
        setFormFields([...formFields]);
    };

    return { updateRowTitle, updateColumnTitle, updateTabularRowTitle, updateTabularColumnTitle, addColumn, addRow, deleteColumn, updateAllowMultipleSelectionMatrixField, deleteRow, updateTabularInputValue, addTabularRow, addTabularColumn, deleteTabularRow, deleteTabularColumn };
}
