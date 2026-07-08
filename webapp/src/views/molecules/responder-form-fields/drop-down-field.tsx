'use client';

import * as React from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@app/shadcn/components/ui/collapsible';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import Choice from '@app/views/atoms/choice';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { scrollToDivById } from '@app/utils/scroll-utils';
import { ChevronDown } from 'lucide-react';
import QuestionWrapper from './question-wrapper';

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
                // The chosen answer is content — ink, not the action colour.
                color: theme?.primary
            };
        }
        // Placeholder state: legible neutral (ink-3), not the theme tint.
        return { borderColor: theme?.tertiary, color: '#657085' };
    };

    return (
        <QuestionWrapper field={field}>
            <Collapsible open={isOpen} onOpenChange={setIsOpen} className=" space-y-2">
                <CollapsibleTrigger asChild>
                    {/* Same input language as every other field: bordered white
                        rounded-xl box, base/lg type, real button semantics — the old
                        trigger was a text-3xl underline-only div with no keyboard
                        affordance, a different species from the rest of the form. */}
                    <button type="button" style={getTextStyle()} className="flex w-full cursor-pointer items-center justify-between gap-4 rounded-xl border bg-white px-4 py-3 text-left text-base outline-none transition-shadow focus-visible:ring-2 lg:text-lg">
                        <span className="truncate">{choiceValue ? choiceValue : 'Select an option'}</span>
                        <ChevronDown className={`duration-400 h-5 w-5 shrink-0 transition ${isOpen ? 'rotate-180' : ''}`} style={{ color: theme?.secondary }} />
                    </button>
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
