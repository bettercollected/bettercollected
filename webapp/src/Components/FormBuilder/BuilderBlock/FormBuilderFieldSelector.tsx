import React, { useCallback, useEffect, useState } from 'react';

import { batch } from 'react-redux';

import useArrowsToSelectOption from '@app/lib/hooks/use-arrows-to-select-option';
import useClickOutsideMenu from '@app/lib/hooks/use-click-outside-menu';
import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetBuilderMenuState, setUpdateField } from '@app/store/form-builder/actions';
import { selectActiveFieldIndex, selectFields, selectMenuState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { convertPlaceholderToDisplayValue, getPreviousField } from '@app/utils/formBuilderBlockUtils';

export default function FormBuilderFieldSelector({ field, searchQuery = '' }: { field: IFormFieldState; searchQuery: string }) {
    const pipingFieldMenuState: any = useAppSelector(selectMenuState('pipingFields'));

    const formFields = useAppSelector(selectFields);

    const dispatch = useAppDispatch();
    const fields = Object.values(formFields);
    const activeFieldPosition = useAppSelector(selectActiveFieldIndex);

    useClickOutsideMenu('field-selector');

    const [selectedFieldIndex, setSelectedFieldIndex] = useState(0);
    const getFilteredInputFields = () => {
        const filteredFields: Array<any> = [];
        fields.forEach((field) => {
            if (field.type.includes('input_') && ![FormBuilderTagNames.INPUT_FILE_UPLOAD, FormBuilderTagNames.INPUT_RANKING].includes(field?.type) && field?.position < activeFieldPosition) {
                const x: any = {
                    fieldId: field.id
                };
                const previousField = getPreviousField(fields, field);
                let text = field?.properties?.placeholder;
                if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                    text = previousField?.value;
                }
                x.value = convertPlaceholderToDisplayValue(fields, text) || field?.type;
                x.type = field.type;
                if (x.value.match(searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') || '')) {
                    filteredFields.push(x);
                }
            }
        });
        return filteredFields;
    };

    const [selectionFields, setSelectionFields] = useState(getFilteredInputFields());

    const scrollToSelectedItem = (index: number | string) => {
        const selectedItem = document.getElementById('list-item-' + index);
        if (selectedItem) {
            selectedItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    };

    const handleNext = useCallback(
        (e: any) => {
            const newIndex = (selectedFieldIndex + 1) % selectionFields.length;
            setSelectedFieldIndex(newIndex);
            scrollToSelectedItem(newIndex);
        },
        [selectionFields, selectedFieldIndex]
    );

    const handlePrevious = useCallback(
        (e: any) => {
            const newIndex = (selectedFieldIndex - 1 + selectionFields.length) % selectionFields.length;
            setSelectedFieldIndex(newIndex);
            scrollToSelectedItem(newIndex);
        },
        [selectionFields, selectedFieldIndex]
    );

    const handleSelectField = (e: any) => {
        onClickField(selectionFields[selectedFieldIndex]);
    };

    useArrowsToSelectOption(handleSelectField, handleNext, handlePrevious);

    useEffect(() => {
        setSelectionFields(getFilteredInputFields());
    }, [searchQuery]);
    const replaceLastAt = (inputString: string, replacement: string) => {
        const lastAtIndex = inputString.lastIndexOf('@');

        if (lastAtIndex !== -1) {
            return inputString.substring(0, lastAtIndex) + replacement + inputString.substring(lastAtIndex + 1);
        }
        return inputString;
    };

    const replaceNthAt = (inputString: string, replacement: string, nthOccurrence: number) => {
        return inputString.replace(new RegExp('((?:[^@]*@){' + (nthOccurrence - 1) + '}[^@]*)@'), '$1' + replacement);
    };
    const onClickField = (inputField: any) => {
        batch(() => {
            dispatch(
                setUpdateField({
                    ...field,
                    value: replaceNthAt(field.value || '', `{{ ${inputField.fieldId} }}`, pipingFieldMenuState?.atPosition ?? 1)
                })
            );
            dispatch(resetBuilderMenuState());
        });
    };

    return (
        <>
            <div
                id="field-selector"
                // style={{
                //     position: 'fixed',
                //     left: pipingFieldMenuState?.pos?.left,
                //     top: pipingFieldMenuState?.pos?.top + 24
                // }}
                className={`max-h-48 p-2 absolute rounded w-[300px] bg-white overflow-auto drop-shadow-lg top-full z-[100]`}
            >
                <div className="text-gray-600 font-bold px-4 py-2 ">Mention a field</div>
                <div className="flex flex-col">
                    {selectionFields.map((inputField: any, index) => (
                        <div
                            id={'list-item-' + index}
                            className={`px-4 py-2 cursor-pointer truncate bg-white hover:bg-black-200 ${selectedFieldIndex === index ? '!bg-black-100' : ''} text-base font-normal  text-black-800`}
                            key={inputField.fieldId}
                            onClick={() => {
                                onClickField(inputField);
                            }}
                        >
                            {inputField?.value}
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
}
