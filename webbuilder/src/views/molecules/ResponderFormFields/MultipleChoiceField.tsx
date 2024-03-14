import { useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import { useFormTheme } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { Check } from '@app/views/atoms/Icons/Check';

import QuestionWrapper from './QuestionQwrapper';

const MultipleChoiceField = ({ field }: { field: FormField }) => {
    const { addFieldChoicesAnswer } = useFormResponse();
    const theme = useFormTheme();
    const [selectedItems, setSelectedItems] = useState<Array<string>>([]);

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
                            background: selectedItems.includes(choice.value || '')
                                ? theme?.tertiary
                                : '',
                            borderColor: theme?.tertiary
                        }}
                        className="flex cursor-pointer justify-between rounded-xl border p-2 px-4"
                        key={choice.value}
                        onClick={() => handleClick(choice.value || '')}
                    >
                        {choice.value}{' '}
                        {selectedItems.includes(choice.value || '') && <Check />}
                    </div>
                ))}
            </div>
        </QuestionWrapper>
    );
};

export default MultipleChoiceField;

// optional
// const MultipleChoiceField = ({ field }: { field: FormField }) => {
//     const { addFieldChoiceAnswer } = useFormResponse();
//     const theme = useFormTheme();
//     return (
//         <QuestionWrapper field={field}>
//             <select
//                 className="w-full space-y-2 overflow-hidden border-0 p-0"
//                 multiple
//                 onChange={(e) =>
//                     console.log(
//                         e
//                         // Array.from(e.target.selectedOptions).map(
//                         //     (selectedOptions) => selectedOptions.value
//                         // )
//                     )
//                 }
//             >
//                 {field.properties?.choices?.map((choice) => {
//                     return (
//                         <option
//                             style={{ borderColor: theme?.tertiary }}
//                             className="cursor-pointer rounded-xl border p-2 px-4 checked:bg-red-500 hover:bg-black-700 active:bg-yellow-500"
//                             value={choice.value}
//                         >
//                             {choice.value}
//                         </option>
//                     );
//                 })}
//             </select>
//         </QuestionWrapper>
//     );
// };
