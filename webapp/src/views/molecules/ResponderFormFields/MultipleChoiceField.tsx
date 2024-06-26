import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import Choice from '@app/views/atoms/ResponderFormFields/Choice';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { scrollToDivById } from '@app/utils/scrollUtils';
import QuestionWrapper from './QuestionQwrapper';

const MultipleChoiceField = ({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) => {
    const { addFieldChoiceAnswer, addOtherChoiceAnswer, formResponse, removeAnswer } = useFormResponse();
    const { theme } = useFormState();

    const standardForm = useAppSelector(selectForm);
    const currentSlide = standardForm.fields![slideIndex];

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
            if (standardForm?.fields?.[slideIndex]?.properties?.fields?.length !== field.index + 1) scrollToDivById(standardForm?.fields?.[slideIndex]?.properties?.fields?.[field.index + 1]?.id);
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
                        type="text"
                        value={otherOption}
                        placeholder={`Other`}
                        onChange={(e: any) => {
                            if (!e.target.value) {
                                removeAnswer(field.id);
                                return;
                            }
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
