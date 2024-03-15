import { useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import { useFormTheme } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { Check } from '@app/views/atoms/Icons/Check';

import QuestionWrapper from './QuestionQwrapper';

const MultipleChoiceField = ({ field }: { field: FormField }) => {
    const { addFieldChoicesAnswer, formResponse } = useFormResponse();
    const theme = useFormTheme();
    const [selectedItems, setSelectedItems] = useState<Array<string>>([]);

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        return formResponse?.answers[field.id]?.choice;
    };

    const handleClick = (item: string) => {
        const isSelected = selectedItems.includes(item);
        setSelectedItems(() => {
            const updatedSelection = isSelected
                ? selectedItems.filter((selectedItem: string) => selectedItem !== item)
                : [...selectedItems, item];
            addFieldChoicesAnswer(field.id, updatedSelection);
            return updatedSelection;
        });
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 overflow-hidden border-0 p-0">
                {field.properties?.choices?.map((choice) => (
                    <div
                        style={{
                            background: selectedItems.includes(choice.id || '')
                                ? theme?.tertiary
                                : '',
                            borderColor: theme?.tertiary
                        }}
                        className="flex cursor-pointer justify-between rounded-xl border p-2 px-4"
                        key={choice.id}
                        onClick={() => handleClick(choice.id || '')}
                    >
                        {choice.value}{' '}
                        {selectedItems.includes(choice.id || '') && <Check />}
                    </div>
                ))}
            </div>
        </QuestionWrapper>
    );
};

export default MultipleChoiceField;