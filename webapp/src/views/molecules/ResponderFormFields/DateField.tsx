import { useCallback, useEffect, useState } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { getFormattedDate, getUnformattedDate, validateDate } from '@app/utils/dateUtils';

import QuestionWrapper from './QuestionQwrapper';
import { useDebounceCallback } from 'usehooks-ts';
import { cn } from '@app/shadcn/util/lib';

interface IDateField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
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
                }, 200);
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
            <div className="flex flex-row items-center gap-4" id={`input-field-${field.id}`}>
                <FieldInput id={isBuilder ? 'day' : `day-${field.id}`} type="number" placeholder="DD" className={cn(inputClassName, isBuilder && 'pointer-events-none')} value={getUnformattedDate(answer)[2]} onChange={(e) => handleDateChange(e, 'day')} />
                <div
                    style={{
                        background: slide?.properties?.theme?.secondary || theme?.secondary
                    }}
                    className="h-0.5 w-2"
                />
                <FieldInput
                    id={isBuilder ? 'month' : `month-${field.id}`}
                    type="number"
                    placeholder="MM"
                    className={cn(inputClassName, isBuilder && 'pointer-events-none')}
                    value={getUnformattedDate(answer)[1]}
                    onChange={(e) => handleDateChange(e, 'month')}
                />
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
                    value={getUnformattedDate(answer)[0]}
                    className={cn(inputClassName, isBuilder && 'pointer-events-none', 'w-24')}
                    onChange={(e) => handleDateChange(e, 'year')}
                    onBlur={(e) => handleBlurValidation(e, '')}
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
