import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import ChoiceRadioGroup from '@app/views/atoms/choice-radio-group';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { scrollToDivById } from '@app/utils/scroll-utils';
import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { cn } from '@app/shadcn/util/lib';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

const MultipleChoiceField = ({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) => {
    const { addFieldChoiceAnswer, addOtherChoiceAnswer, formResponse, removeAnswer } = useFormResponse();
    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const tokens = styleTokens(theme?.style);

    const standardForm = useAppSelector(selectForm);
    const currentSlide = standardForm.fields![slideIndex];

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        return formResponse?.answers[field.id]?.choice?.value;
    };

    const otherOption = formResponse?.answers?.[field.id]?.choice?.other || '';

    const handleClick = (item: string, moveOn = true) => {
        addFieldChoiceAnswer(field.id, item);
        if (!moveOn) return;
        setTimeout(() => {
            if (standardForm?.fields?.[slideIndex]?.properties?.fields?.length !== field.index + 1) scrollToDivById(standardForm?.fields?.[slideIndex]?.properties?.fields?.[field.index + 1]?.id);
        }, 200);
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 p-0">
                {/* A real radio group: one tab stop, arrow keys move between the
                    options, and each option is announced as a radio button. */}
                <WithQuestionLabel>
                    {({ control }) => (
                        <ChoiceRadioGroup
                            labelProps={control}
                            theme={theme}
                            value={getSelectedValue() ?? null}
                            onChange={(value, { viaArrowKeys }) => handleClick(value, !viaArrowKeys)}
                            className={cn(tokens.ruledChoices ? '' : 'space-y-2')}
                            options={(field.properties?.choices ?? []).map((choice, index) => ({ key: choice.id ?? String(index), value: choice.id ?? '', label: choice.value ? choice.value : `Item ${index + 1}`, lang: choice.value ? contentLang : undefined }))}
                        />
                    )}
                </WithQuestionLabel>
                {field?.properties?.allowOtherChoice && (
                    <FieldInput
                        type="text"
                        value={otherOption}
                        placeholder={t('FIELD.OTHER')}
                        aria-label={t('FIELD.OTHER')}
                        onChange={(e: any) => {
                            if (!e.target.value) {
                                removeAnswer(field.id);
                                return;
                            }
                            addOtherChoiceAnswer(field.id, e.target.value);
                        }}
                        $formTheme={theme}
                        className="flex min-h-12 justify-between border px-4 py-3 text-base"
                    />
                )}
            </div>
        </QuestionWrapper>
    );
};

export default MultipleChoiceField;
