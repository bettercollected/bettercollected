import { format } from 'date-fns';
import { CalendarIcon } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';

import QuestionWrapper from './question-wrapper';
import { ThemedCalendar } from './themed-calendar';

interface IDateField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

function DateFieldSection({ field, isBuilder }: IDateField) {
    const { theme } = useFormState();
    const { formResponse, addFieldDateAnswer } = useFormResponse();
    const answer = (formResponse.answers && formResponse.answers[field.id]?.date) || '';
    const { nextField } = useResponderState();

    const [date, setDate] = useState<Date | undefined>(answer ? new Date(answer) : undefined);
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);

    useEffect(() => {
        if (answer) {
            setDate(new Date(answer));
        } else {
            setDate(undefined);
        }
    }, [answer]);

    const handleSelect = useCallback(
        (selectedDate: Date | undefined) => {
            setDate(selectedDate);
            if (selectedDate) {
                const offset = selectedDate.getTimezoneOffset();
                const adjustedDate = new Date(selectedDate.getTime() - offset * 60 * 1000);
                const dateString = adjustedDate.toISOString().split('T')[0];

                addFieldDateAnswer(field.id, dateString);
                setIsPopoverOpen(false);
                if (!isBuilder) {
                    setTimeout(() => {
                        nextField();
                    }, 200);
                }
            }
        },
        [addFieldDateAnswer, field.id, isBuilder, nextField]
    );

    const secondaryColor = theme?.secondary;
    const tertiaryColor = theme?.tertiary;

    return (
        <div className="flex flex-col gap-1">
            <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
                <PopoverTrigger asChild disabled={isBuilder}>
                    <button
                        type="button"
                        className={cn(
                            'flex w-full cursor-pointer items-center gap-2 rounded-xl border bg-white px-4 py-3 text-base outline-none transition-shadow focus-visible:ring-2 lg:text-lg',
                            isBuilder && 'pointer-events-none'
                        )}
                        style={{
                            borderColor: tertiaryColor,
                            // Chosen date is content (ink); empty state a legible neutral.
                            color: date ? theme?.primary : '#657085'
                        }}
                    >
                        <CalendarIcon
                            className="h-6 w-6 shrink-0"
                            style={{ color: secondaryColor }}
                        />
                        {date ? (
                            // The chosen date is the answer — ink, not the action colour.
                            <span style={{ color: theme?.primary }}>{format(date, 'PPP')}</span>
                        ) : (
                            <span style={{ color: '#657085' }}>Pick a date</span>
                        )}
                    </button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                    <ThemedCalendar
                        mode="single"
                        selected={date}
                        onSelect={handleSelect}
                        autoFocus
                    />
                </PopoverContent>
            </Popover>
        </div>
    );
}

const DateField = ({ field, slide, isBuilder = false }: IDateField) => {
    return isBuilder ? (
        <DateFieldSection field={field} slide={slide} isBuilder={isBuilder} />
    ) : (
        <QuestionWrapper field={field}>
            <div onSubmit={(e) => e.preventDefault()}>
                <DateFieldSection field={field} slide={slide} isBuilder={isBuilder} />
            </div>
        </QuestionWrapper>
    );
};
export default DateField;
