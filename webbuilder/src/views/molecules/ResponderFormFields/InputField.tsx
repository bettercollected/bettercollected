import { FieldTypes, FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { getPlaceholderValueForField } from '@app/utils/formUtils';

import QuestionWrapper from './QuestionQwrapper';

export default function InputField({ field }: { field: FormField }) {
    const {
        formResponse,
        addFieldTextAnswer,
        addFieldEmailAnswer,
        addFieldNumberAnswer,
        addFieldURLAnswer,
        removeAnswer
    } = useFormResponse();

    const { nextField, currentField } = useResponderState();
    const handleChange = (e: any) => {
        if (!e.target.value) {
            removeAnswer(field.id);
            return;
        }
        switch (field.type) {
            case FieldTypes.LINK:
                addFieldURLAnswer(field.id, e.target.value);
                break;
            case FieldTypes.NUMBER:
                addFieldNumberAnswer(field.id, e.target.value);
                break;
            case FieldTypes.EMAIL:
                addFieldEmailAnswer(field.id, e.target.value);
                break;
            case FieldTypes.SHORT_TEXT:
            case FieldTypes.LONG_TEXT:
                addFieldTextAnswer(field.id, e.target.value);
                break;
            default:
                break;
        }
    };

    const getFieldValue = () => {
        switch (field.type) {
            case FieldTypes.LINK:
                return (
                    (formResponse.answers && formResponse.answers[field.id]?.url) || ''
                );
            case FieldTypes.NUMBER:
                return (
                    (formResponse.answers && formResponse.answers[field.id]?.number) ||
                    ''
                );
            case FieldTypes.EMAIL:
                return (
                    (formResponse.answers && formResponse.answers[field.id]?.email) ||
                    ''
                );
            case FieldTypes.SHORT_TEXT:
            case FieldTypes.LONG_TEXT:
                return (
                    (formResponse.answers && formResponse.answers[field.id]?.text) || ''
                );
            default:
                break;
        }
    };

    const TextFields = [FieldTypes.LONG_TEXT, FieldTypes.SHORT_TEXT];

    return (
        <QuestionWrapper field={field}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    nextField();
                }}
            >
                <FieldInput
                    id={`input-field-${field.id}`}
                    type={
                        TextFields.includes(field.type ?? FieldTypes.SHORT_TEXT)
                            ? 'text'
                            : field.type
                    }
                    placeholder={
                        field?.properties?.placeholder ||
                        getPlaceholderValueForField(field.type)
                    }
                    autoFocus={currentField === field.index}
                    className="mt-4"
                    multiple={field.type === FieldTypes.LONG_TEXT}
                    value={getFieldValue()}
                    onChange={(e: any) => handleChange(e)}
                />
            </form>
        </QuestionWrapper>
    );
}
