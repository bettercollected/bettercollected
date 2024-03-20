import { useEffect, useState } from 'react';

import { FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import {
    getFormattedDate,
    getUnformattedDate,
    validateDate
} from '@app/utils/dateUtils';

import QuestionWrapper from './QuestionQwrapper';

interface IDateField {
    field: FormField;
    slide?: FormField;
    disabled?: boolean;
}
type dateType = 'day' | 'month' | 'year' | '';

function DateFieldSection({ field, slide, disabled }: IDateField) {
    const { theme } = useFormState();
    const { formResponse, addFieldDateAnswer } = useFormResponse();
    const [date, setDate] = useState({
        day: '',
        month: '',
        year: ''
    });
    const [errorMessage, setErrorMessage] = useState('');

    useEffect(() => {
        const timeout = setTimeout(() => setErrorMessage(''), 2000);
        return () => clearTimeout(timeout);
    }, [errorMessage]);

    useEffect(() => {
        const formResponseDate =
            formResponse.answers && formResponse.answers[field.id]?.date;
        if (formResponseDate) {
            const unFormattedDate = getUnformattedDate(formResponseDate);
            setDate({
                day: unFormattedDate?.[0] ?? '',
                month: unFormattedDate?.[1] ?? '',
                year: unFormattedDate?.[2] ?? ''
            });
        }
    }, [formResponse.answers]);

    function handleDateChange(e: any, type: dateType) {
        const errorMsg = validateDate(e.target.value, type);
        if (errorMsg) {
            setErrorMessage(errorMsg);
        } else {
            setDate((prevDate) => {
                const newDate = {
                    ...prevDate,
                    [type]: e.target.value
                };
                addFieldDateAnswer(field.id, getFormattedDate(newDate));
                return newDate;
            });
        }
    }

    function handleBlurValidation(e: any, type: dateType): void {
        const errorMsg = validateDate(e.target.value, type);
        if (errorMsg) {
            setErrorMessage(errorMsg);
            setDate({ ...date, year: '' });
        }
    }

    const inputClassName = 'w-14 border-0 border-b-2 px-0 text-[32px] text-center';

    return (
        <div className="flex flex-col gap-1">
            <div className="flex flex-row items-center gap-4">
                <FieldInput
                    type="number"
                    placeholder="DD"
                    className={inputClassName}
                    value={date.day}
                    onChange={(e) => handleDateChange(e, 'day')}
                    disabled={disabled}
                />
                <div
                    style={{
                        background:
                            slide?.properties?.theme?.secondary || theme?.secondary
                    }}
                    className="h-0.5 w-2"
                />
                <FieldInput
                    type="number"
                    placeholder="MM"
                    className={inputClassName}
                    value={date.month}
                    onChange={(e) => handleDateChange(e, 'month')}
                    disabled={disabled}
                />
                <div
                    style={{
                        background:
                            slide?.properties?.theme?.secondary || theme?.secondary
                    }}
                    className="h-0.5 w-2"
                />
                <FieldInput
                    type="number"
                    placeholder="YYYY"
                    value={date.year}
                    className={`${inputClassName} w-24`}
                    onChange={(e) => handleDateChange(e, 'year')}
                    onBlur={(e) => handleBlurValidation(e, '')}
                    disabled={disabled}
                />
            </div>
            {errorMessage && (
                <span className="text-sm text-red-500 ">{errorMessage}</span>
            )}
        </div>
    );
}

const DateField = ({ field, slide, disabled = false }: IDateField) => {
    const { nextField } = useResponderState();

    return disabled ? (
        <DateFieldSection field={field} slide={slide} disabled={disabled} />
    ) : (
        <QuestionWrapper field={field}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    nextField();
                }}
            >
                <DateFieldSection field={field} slide={slide} disabled={disabled} />
            </form>
        </QuestionWrapper>
    );
};
export default DateField;
