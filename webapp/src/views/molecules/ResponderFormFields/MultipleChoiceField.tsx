import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormTheme } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import Choice from '@app/views/atoms/ResponderFormFields/Choice';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import QuestionWrapper from './QuestionQwrapper';

const MultipleChoiceField = ({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) => {
    const { addFieldChoiceAnswer, addOtherChoiceAnswer, formResponse } = useFormResponse();
    const theme = useFormTheme();

    const standardForm = useAppSelector(selectForm);
    const currentSlide = standardForm.fields![slideIndex];

    const { nextField } = useResponderState();

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        return formResponse?.answers[field.id]?.choice?.value;
    };

    const otherOption = formResponse?.answers?.[field.id]?.choice?.other || '';

    const handleClick = (item: string) => {
        addFieldChoiceAnswer(field.id, item);
        setTimeout(() => {
            nextField();
        }, 200);
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 overflow-hidden border-0 p-0">
                {field.properties?.choices?.map((choice, index) => {
                    const isSelected = getSelectedValue() === choice.id;
                    return <Choice key={choice.id} isSelected={isSelected} theme={theme} choice={choice} onClick={handleClick} index={index} />;
                })}
                {field?.properties?.allowOtherChoice && (
                    <FieldInput
                        $slide={currentSlide}
                        type="text"
                        $formTheme={theme}
                        textColor={currentSlide.properties?.theme?.secondary || theme?.secondary || 'text-black-500'}
                        value={otherOption}
                        placeholder={`Other`}
                        onChange={(e: any) => {
                            addOtherChoiceAnswer(field.id, e.target.value);
                        }}
                        className={`flex justify-between rounded-xl border p-2 px-4 text-base`}
                    />
                )}
            </div>
        </QuestionWrapper>
    );
};

export default MultipleChoiceField;
