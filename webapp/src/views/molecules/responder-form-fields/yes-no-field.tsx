import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { scrollToDivById } from '@app/utils/scroll-utils';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import ChoiceRadioGroup from '@app/views/atoms/choice-radio-group';
import { yesNoChoices } from '@app/utils/yes-no-choices';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

const YesNoField = ({ field }: { field: StandardFormFieldDto }) => {
    const { addFieldBooleanAnswer, formResponse } = useFormResponse();
    const { theme } = useFormState();

    const form = useAppSelector(selectForm);
    const tokens = styleTokens(theme?.style);
    const { currentSlide } = useResponderState();
    const { t } = useRespondentLanguage();

    // null (not undefined) when unanswered, so the RadioGroup stays controlled.
    const getValue = () => formResponse?.answers?.[field.id]?.boolean ?? null;

    return (
        <QuestionWrapper field={field}>
            <WithQuestionLabel>
                {({ control }) => (
                    <ChoiceRadioGroup
                        labelProps={control}
                        theme={theme}
                        value={getValue()}
                        className={tokens.ruledChoices ? 'flex w-full flex-col' : 'flex w-full max-w-xs flex-col gap-2'}
                        // The stored values stay "Yes"/"No" (they map to true/false); only the label follows the respondent's language.
                        options={yesNoChoices(field).map((choice, index) => ({
                            key: String(index),
                            value: choice.value === 'Yes',
                            label: choice.value === 'Yes' ? t('FIELD.YES') : choice.value === 'No' ? t('FIELD.NO') : choice.value
                        }))}
                        onChange={(value, { viaArrowKeys }) => {
                            addFieldBooleanAnswer(field.id, !!value);
                            if (viaArrowKeys) return;
                            setTimeout(() => {
                                if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                            }, 200);
                        }}
                    />
                )}
            </WithQuestionLabel>
        </QuestionWrapper>
    );
};

export default YesNoField;
