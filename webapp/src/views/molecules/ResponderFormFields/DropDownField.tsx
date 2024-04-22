'use client';

import * as React from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@app/shadcn/components/ui/collapsible';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { ChevronDown } from '@app/views/atoms/Icons/ChevronDown';
import Choice from '@app/views/atoms/ResponderFormFields/Choice';

import QuestionWrapper from './QuestionQwrapper';
import { scrollToDivById } from '@app/utils/scrollUtils';
import { useAppSelector } from '@app/store/hooks';
import { selectForm } from '@app/store/forms/slice';

export default function DropDownField({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    const [isOpen, setIsOpen] = React.useState(false);
    const { theme } = useFormState();
    const { addFieldChoiceAnswer, formResponse } = useFormResponse();

    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        const selectedChoiceId = formResponse?.answers[field.id]?.choice?.value;
        const choice = field?.properties?.choices?.find((choice) => choice.id === selectedChoiceId);
        const choiceIndex = field?.properties?.choices?.findIndex((choice) => choice.id === selectedChoiceId);

        function getChoiceValue() {
            return choice?.value ? choice?.value : `Item ${(choiceIndex ?? 0) + 1}`;
        }

        return selectedChoiceId ? getChoiceValue() : '';
    };

    const choiceValue = getSelectedValue();

    const handleClick = (choiceId: string) => {
        addFieldChoiceAnswer(field.id, choiceId);
        setIsOpen(false);
        setTimeout(() => {
            if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
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
                    <div style={getTextStyle()} className="flex cursor-pointer items-center justify-between space-x-4 border-b-[1px] text-3xl">
                        {choiceValue ? choiceValue : 'Select an Option'}
                        <ChevronDown className={`duration-400 h-6 w-7 transition ${isOpen ? 'rotate-180' : ''}`} style={{ color: theme?.secondary }} />
                    </div>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-2">
                    {field.properties?.choices?.map((choice, index) => {
                        return <Choice key={choice.id} index={index} isSelected={choice.id === choiceValue} theme={theme} choice={choice} onClick={handleClick} />;
                    })}
                </CollapsibleContent>
            </Collapsible>
        </QuestionWrapper>
    );
}
