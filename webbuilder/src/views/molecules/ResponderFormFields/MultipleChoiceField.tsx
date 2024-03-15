import { useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import { FieldInput, Input } from '@app/shadcn/components/ui/input';
import { useFormTheme, useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { Check } from '@app/views/atoms/Icons/Check';

import QuestionWrapper from './QuestionQwrapper';

const MultipleChoiceField = ({ field }: { field: FormField }) => {
    const { addFieldChoiceAnswer, addOtherChoiceAnswer, formResponse } =
        useFormResponse();
    const theme = useFormTheme();

    const { standardForm } = useStandardForm();
    const currentSlide = standardForm.fields![formResponse?.currentSlide];

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        return formResponse?.answers[field.id]?.choice?.value;
    };

    const otherOption = formResponse?.answers?.[field.id]?.choice?.other || '';

    const handleClick = (item: string) => {
        addFieldChoiceAnswer(field.id, item);
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 overflow-hidden border-0 p-0">
                {field.properties?.choices?.map((choice) => {
                    const isSelected = getSelectedValue() === choice.id;
                    return (
                        <div
                            style={{
                                background: isSelected ? theme?.tertiary : '',
                                borderColor: theme?.tertiary
                            }}
                            className="flex cursor-pointer justify-between rounded-xl border p-2 px-4"
                            key={choice.id}
                            onClick={() => handleClick(choice.id || '')}
                        >
                            {choice.value} {isSelected && <Check />}
                        </div>
                    );
                })}
                {field?.properties?.allowOtherChoice && (
                    <FieldInput
                        $slide={currentSlide}
                        type="text"
                        $formTheme={theme}
                        textColor={
                            currentSlide.properties?.theme?.secondary ||
                            theme?.secondary ||
                            'text-black-500'
                        }
                        value={otherOption}
                        placeholder={`Other`}
                        onChange={(e: any) => {
                            addOtherChoiceAnswer(field.id, e.target.value);
                        }}
                        className={`flex justify-between rounded-xl border p-2 px-4`}
                    />
                )}
            </div>
        </QuestionWrapper>
    );
};

export default MultipleChoiceField;
