import { useCallback, useEffect, useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { getFormattedDate, getUnformattedDate, validateDate } from '@app/utils/dateUtils';

import QuestionWrapper from './QuestionQwrapper';
import { useDebounceCallback } from 'usehooks-ts';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';

interface IDateField {
    field: FormField;
    slide?: FormField;
    isBuilder?: boolean;
}
type dateType = 'day' | 'month' | 'year' | '';

function DateFieldSection({ field, slide, isBuilder }: IDateField) {
    const { theme } = useFormState();
    const { formResponse, addFieldDateAnswer } = useFormResponse();
    const answer = (formResponse.answers && formResponse.answers[field.id]?.date) || '';
    const { nextField } = useResponderState();

    const [errorMessage, setErrorMessage] = useState('');

    useEffect(() => {
        const timeout = setTimeout(() => setErrorMessage(''), 2000);
        return () => clearTimeout(timeout);
    }, [errorMessage]);

    const onChangeOfDateField = useCallback(
        (type: dateType) => {
            if (type === 'year') {
                return;
            }
            function getNextType() {
                switch (type) {
                    case 'day':
                        return 'month';
                    case 'month':
                        return 'year';
                    case 'year':
                        '';
                }
            }
            const fieldId = isBuilder ? getNextType() : `${getNextType()}-${field.id}`;
            window.setTimeout(() => {
                fieldId && document.getElementById(fieldId)?.focus();
            }, 0);
        },
        [formResponse.answers]
    );

    const onChangeDateFieldDebounced = useDebounceCallback(onChangeOfDateField, 2000);

    function handleDateChange(e: any, type: dateType) {
        e.preventDefault();
        const errorMsg = validateDate(e.target.value, type);
        if (errorMsg) {
            setErrorMessage(errorMsg);
        } else {
            addFieldDateAnswer(field.id, getFormattedDate(e.target.value, answer, type));
            onChangeDateFieldDebounced(type);
            if (type === 'year') {
                window.setTimeout(() => {
                    const nextFieldId = slide?.properties?.fields![field.index].id;
                    nextField();
                    document.getElementById(`input-field-${nextFieldId}`)?.focus();
                }, 2000);
            }
        }
    }

    function handleBlurValidation(e: any, type: dateType): void {
        const errorMsg = validateDate(e.target.value, type);
        if (errorMsg) {
            setErrorMessage(errorMsg);
            addFieldDateAnswer(field.id, getFormattedDate('', answer, 'year'));
        }
    }

    const inputClassName = 'w-14 border-0 border-b-2 px-0 text-[32px] text-center';

    return (
        <div className="flex flex-col gap-1">
            <div className="flex flex-row items-center gap-4">
                <FieldInput id={isBuilder ? 'day' : `day-${field.id}`} type="number" placeholder="DD" className={inputClassName} value={getUnformattedDate(answer)[0]} onChange={(e) => handleDateChange(e, 'day')} disabled={isBuilder} />
                <div
                    style={{
                        background: slide?.properties?.theme?.secondary || theme?.secondary
                    }}
                    className="h-0.5 w-2"
                />
                <FieldInput id={isBuilder ? 'month' : `month-${field.id}`} type="number" placeholder="MM" className={inputClassName} value={getUnformattedDate(answer)[1]} onChange={(e) => handleDateChange(e, 'month')} disabled={isBuilder} />
                <div
                    style={{
                        background: slide?.properties?.theme?.secondary || theme?.secondary
                    }}
                    className="h-0.5 w-2"
                />
                <FieldInput
                    id={isBuilder ? 'year' : `year-${field.id}`}
                    type="number"
                    placeholder="YYYY"
                    value={getUnformattedDate(answer)[2]}
                    className={`${inputClassName} w-24`}
                    onChange={(e) => handleDateChange(e, 'year')}
                    onBlur={(e) => handleBlurValidation(e, '')}
                    disabled={isBuilder}
                />
            </div>
            {errorMessage && <span className="text-sm text-red-500 ">{errorMessage}</span>}
        </div>
    );
}

const DateField = ({ field, slide, isBuilder = false }: IDateField) => {
    const { nextField } = useResponderState();

    return isBuilder ? (
        <DateFieldSection field={field} slide={slide} isBuilder={isBuilder} />
    ) : (
        <QuestionWrapper field={field}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    nextField();
                }}
            >
                <DateFieldSection field={field} slide={slide} isBuilder={isBuilder} />
            </form>
        </QuestionWrapper>
    );
};
export default DateField;
