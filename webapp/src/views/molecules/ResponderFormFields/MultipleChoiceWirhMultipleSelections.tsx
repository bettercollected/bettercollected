import { FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormTheme, useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import Choice from '@app/views/atoms/ResponderFormFields/Choice';

import QuestionWrapper from './QuestionQwrapper';

export default function MultipleChoiceWithMultipleSelection({
    field,
    slideIndex
}: {
    field: FormField;
    slideIndex: number;
}) {
    const { addFieldChoicesAnswer, addOtherChoicesAnswer, formResponse } =
        useFormResponse();

    const theme = useFormTheme();

    const { standardForm } = useStandardForm();
    const currentSlide = standardForm.fields![slideIndex];

    const getSelectedValues = () => {
        if (!formResponse.answers) {
            return null;
        }
        return formResponse?.answers[field.id]?.choices?.values || [];
    };

    const selectedValues = getSelectedValues() || [];

    const otherOption = formResponse?.answers?.[field.id]?.choices?.other || '';

    const handleClick = (choiceId: string) => {
        const index = selectedValues.indexOf(choiceId);

        if (index === -1) {
            selectedValues.push(choiceId);
        } else {
            selectedValues.splice(index, 1);
        }
        addFieldChoicesAnswer(field.id, selectedValues);
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 overflow-hidden border-0 p-0">
                {field.properties?.choices?.map((choice, index) => {
                    const isSelected = selectedValues.includes(choice.id);
                    return (
                        <Choice
                            key={choice.id}
                            isSelected={isSelected}
                            theme={theme}
                            choice={choice}
                            onClick={handleClick}
                            index={index}
                        />
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
                            addOtherChoicesAnswer(field.id, e.target.value);
                        }}
                        className={`flex justify-between rounded-xl border p-2 px-4`}
                    />
                )}
            </div>
        </QuestionWrapper>
    );
}
