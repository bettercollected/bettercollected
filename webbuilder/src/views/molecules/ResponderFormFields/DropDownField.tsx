'use client';

import * as React from 'react';
import { useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger
} from '@app/shadcn/components/ui/collapsible';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { ChevronDown } from '@app/views/atoms/Icons/ChevronDown';

import QuestionWrapper from './QuestionQwrapper';

export default function DropDownField({ field }: { field: FormField }) {
    const [isOpen, setIsOpen] = React.useState(false);
    const { theme } = useFormState();
    const { addFieldChoiceAnswer } = useFormResponse();
    const [choiceValue, setChoiceValue] = useState('');

    return (
        <QuestionWrapper field={field}>
            <Collapsible open={isOpen} onOpenChange={setIsOpen} className=" space-y-2">
                <CollapsibleTrigger asChild>
                    <div
                        style={{ borderColor: theme?.tertiary, color: theme?.tertiary }}
                        className="flex cursor-pointer items-center justify-between space-x-4 border-b-[1px] text-3xl"
                    >
                        {choiceValue ? choiceValue : 'Select an Option'}
                        <ChevronDown
                            className={`h-6 w-7 ${isOpen ? 'rotate-180' : ''}`}
                            style={{ color: theme?.secondary }}
                        />
                    </div>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-2">
                    {field.properties?.choices?.map((choice) => {
                        return (
                            <div
                                key={choice.id}
                                onClick={() => {
                                    choice.value && setChoiceValue(choice.value);
                                    addFieldChoiceAnswer(field.id, choice.value ?? '');
                                    setIsOpen(false);
                                }}
                                style={{
                                    borderColor: theme?.tertiary
                                }}
                                className={`flex cursor-pointer justify-between rounded-xl border p-2 px-4 active:bg-brand-200`}
                            >
                                {choice.value}
                            </div>
                        );
                    })}
                </CollapsibleContent>
            </Collapsible>
        </QuestionWrapper>
    );
}

// import * as React from 'react';

// import { FormField } from '@app/models/dtos/form';
// import {
//     Select,
//     SelectContent,
//     SelectGroup,
//     SelectItem,
//     SelectLabel,
//     SelectTrigger,
//     SelectValue
// } from '@app/shadcn/components/ui/select';

// import QuestionWrapper from './QuestionQwrapper';

// export default function DropDownField({ field }: { field: FormField }) {
//     return (
//         <QuestionWrapper field={field}>
//             <Select>
//                 <SelectTrigger className="w-[180px]">
//                     <SelectValue placeholder="Select a fruit" />
//                 </SelectTrigger>
//                 <SelectContent>
//                     <SelectGroup>
//                         <SelectItem value="apple">Apple</SelectItem>
//                         <SelectItem value="banana">Banana</SelectItem>
//                         <SelectItem value="blueberry">Blueberry</SelectItem>
//                         <SelectItem value="grapes">Grapes</SelectItem>
//                         <SelectItem value="pineapple">Pineapple</SelectItem>
//                     </SelectGroup>
//                 </SelectContent>
//             </Select>
//         </QuestionWrapper>
//     );
// }
