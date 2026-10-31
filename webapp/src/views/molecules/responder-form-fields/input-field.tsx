import FieldInputWrapper from '@Components/hocs/field-input-wrapper';

import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { READ_ONLY_EMPTY, getRespondentPlaceholder } from '@app/utils/form-utils';

import { useEnterToNextQuestion } from './next-question';
import { useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

/** The input, named by the question it sits in (QuestionWrapper's label context). */
function LabelledInput(props: React.ComponentProps<typeof FieldInputWrapper>) {
    const { control } = useQuestionLabel();
    return <FieldInputWrapper {...props} {...control} />;
}

export default function InputField({ field }: { field: StandardFormFieldDto }) {
    const { formResponse, addFieldTextAnswer, addFieldEmailAnswer, addFieldNumberAnswer, addFieldURLAnswer, removeAnswer } = useFormResponse();

    const form: StandardFormDto = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();
    const { t } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    // A field rule can lock the question and set its value (a 0 is a value then).
    const locked = useFieldRuleStates().isLocked(field.id);
    const handleChange = (value: any) => {
        if (!value) {
            removeAnswer(field.id);
            return;
        }
        switch (field.type) {
            case FieldTypes.LINK:
                addFieldURLAnswer(field.id, value);
                break;
            case FieldTypes.NUMBER:
                addFieldNumberAnswer(field.id, value);
                break;
            case FieldTypes.EMAIL:
                addFieldEmailAnswer(field.id, value);
                break;
            case FieldTypes.SHORT_TEXT:
            case FieldTypes.LONG_TEXT:
                addFieldTextAnswer(field.id, value);
                break;
            default:
                break;
        }
    };

    const getFieldValue = () => {
        switch (field.type) {
            case FieldTypes.LINK:
                return (formResponse.answers && formResponse.answers[field.id]?.url) || '';
            case FieldTypes.NUMBER: {
                const number = formResponse.answers?.[field.id]?.number;
                return locked ? (number ?? '') : number || '';
            }
            case FieldTypes.EMAIL:
                return (formResponse.answers && formResponse.answers[field.id]?.email) || '';
            case FieldTypes.SHORT_TEXT:
            case FieldTypes.LONG_TEXT:
                return (formResponse.answers && formResponse.answers[field.id]?.text) || '';
            default:
                break;
        }
    };

    const value = getFieldValue();
    // A read-only question with no value says so with a dash, not with the prompt "Answer".
    const placeholder = locked && (value === '' || value === undefined || value === null) ? READ_ONLY_EMPTY : field?.properties?.placeholder || getRespondentPlaceholder(field.type, t);
    const TextFields = [FieldTypes.LONG_TEXT, FieldTypes.SHORT_TEXT];
    const theme = form?.theme || form.fields[currentSlide]?.properties?.theme;

    return (
        <QuestionWrapper field={field}>
            {/* No form of its own: Enter moves on to the next question. */}
            <LabelledInput
                id={`input-field-${field.id}`}
                type={TextFields.includes(field.type ?? FieldTypes.SHORT_TEXT) ? 'text' : field.type}
                placeholder={placeholder}
                multiple={field.type === FieldTypes.LONG_TEXT}
                value={value}
                onChange={(value: any) => handleChange(value)}
                onKeyDown={onKeyDown}
            />
        </QuestionWrapper>
    );
}
