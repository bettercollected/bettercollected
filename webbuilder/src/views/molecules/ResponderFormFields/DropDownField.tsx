'use client';

import * as React from 'react';
import { useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger
} from '@app/shadcn/components/ui/collapsible';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { ChevronDown } from '@app/views/atoms/Icons/ChevronDown';
import Choice from '@app/views/atoms/ResponderFormFields/Choice';

import QuestionWrapper from './QuestionQwrapper';

export default function DropDownField({
    field,
    slideIndex
}: {
    field: FormField;
    slideIndex: number;
}) {
    const [isOpen, setIsOpen] = React.useState(false);
    const { theme } = useFormState();
    const { addFieldChoiceAnswer, formResponse } = useFormResponse();

    const { nextField } = useResponderState();

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        const selectedChoiceId = formResponse?.answers[field.id]?.choice?.value;
        return field?.properties?.choices?.find(
            (choice) => choice.id === selectedChoiceId
        )?.value;
    };

    const choiceValue = getSelectedValue();

    const handleClick = (choiceId: string) => {
        addFieldChoiceAnswer(field.id, choiceId);
        setIsOpen(false);
                    nextField();

        setTimeout(() => {
        }, 200);
    };

    const getTextStyle = () => {
        if (choiceValue) {
            return {
                borderColor: theme?.secondary,
                color: theme?.secondary
            };
        }
        return { borderColor: theme?.tertiary, color: theme?.tertiary };
    };

    return (
        <QuestionWrapper field={field}>
            <Collapsible open={isOpen} onOpenChange={setIsOpen} className=" space-y-2">
                <CollapsibleTrigger asChild>
                    <div
                        style={getTextStyle()}
                        className="flex cursor-pointer items-center justify-between space-x-4 border-b-[1px] text-3xl"
                    >
                        {choiceValue ? choiceValue : 'Select an Option'}
                        <ChevronDown
                            className={`duration-400 h-6 w-7 transition ${isOpen ? 'rotate-180' : ''}`}
                            style={{ color: theme?.secondary }}
                        />
                    </div>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-2">
                    {field.properties?.choices?.map((choice) => {
                        return (
                            <Choice
                                key={choice.id}
                                isSelected={choice.id === choiceValue}
                                theme={theme}
                                choice={choice}
                                onClick={handleClick}
                            />
                        );
                    })}
                </CollapsibleContent>
            </Collapsible>
        </QuestionWrapper>
    );
}
