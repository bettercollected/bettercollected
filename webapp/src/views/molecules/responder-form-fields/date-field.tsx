import { format } from 'date-fns';
import { CalendarIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { getInputFieldsById } from '@app/utils/answer-piping';
import { DateRuleContext, getDateRuleError, getDisabledDayMatcher, isoToLocalDate, resolveDateRuleBounds, toIsoDate, todayIso } from '@app/utils/date-rules';

import QuestionWrapper from './question-wrapper';
import { ThemedCalendar } from './themed-calendar';

interface IDateField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

/** Date rules see the answers as this question does (an item's scope inside a repeating group). */
function useDateRuleContext(): DateRuleContext {
    const { formResponse } = useFormResponse();
    const standardForm = useAppSelector(selectForm);
    const fieldsById = useMemo(() => getInputFieldsById(standardForm?.fields), [standardForm?.fields]);
    return { answers: formResponse.answers ?? {}, fieldsById, today: todayIso() };
}

function DateFieldSection({ field, isBuilder }: IDateField) {
    const { theme } = useFormState();
    const { formResponse, addFieldDateAnswer } = useFormResponse();
    const answer = (formResponse.answers && formResponse.answers[field.id]?.date) || '';
    const { nextField } = useResponderState();
    const ruleContext = useDateRuleContext();

    // Answers are calendar days (YYYY-MM-DD): read them as local dates, so
    // the picker never shows the day before west of UTC.
    const [date, setDate] = useState<Date | undefined>(answer ? isoToLocalDate(answer) : undefined);
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);

    useEffect(() => {
        setDate(answer ? isoToLocalDate(answer) : undefined);
    }, [answer]);

    const handleSelect = useCallback(
        (selectedDate: Date | undefined) => {
            setDate(selectedDate);
            if (selectedDate) {
                addFieldDateAnswer(field.id, toIsoDate(selectedDate));
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

    // Days the date rules rule out can't be picked; with no date chosen yet,
    // the calendar opens on the month of the date it is compared with.
    const disabled = isBuilder ? undefined : getDisabledDayMatcher(field, ruleContext);
    const firstBound = isBuilder ? undefined : resolveDateRuleBounds(field, ruleContext).find((b) => b.rule.target === 'field' || b.rule.target === 'date')?.bound;
    const defaultMonth = date ?? (firstBound ? isoToLocalDate(firstBound) : undefined);

    const secondaryColor = theme?.secondary;
    const tertiaryColor = theme?.tertiary;
    const label = field.properties?.label?.trim();
    const buttonId = `date-picker-${field.id}`;

    return (
        <div className="flex flex-col gap-1">
            {label && (
                <label htmlFor={buttonId} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {label}
                </label>
            )}
            <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
                <PopoverTrigger asChild disabled={isBuilder}>
                    <button
                        id={buttonId}
                        type="button"
                        className={cn(
                            'flex w-full cursor-pointer items-center gap-2 rounded-md border bg-white px-4 py-3 text-base outline-none transition duration-150 hover:!border-[color:var(--hover-border)] hover:shadow-[0_1px_3px_rgba(16,24,38,0.10)] focus-visible:ring-2 lg:text-lg',
                            isBuilder && 'pointer-events-none'
                        )}
                        style={{
                            ['--hover-border' as string]: tertiaryColor ?? '#8A94A6',
                            borderColor: '#E3E3E3',
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
                    <ThemedCalendar mode="single" selected={date} onSelect={handleSelect} disabled={disabled} defaultMonth={defaultMonth} autoFocus />
                </PopoverContent>
            </Popover>
        </div>
    );
}

const DateField = ({ field, slide, isBuilder = false }: IDateField) => {
    const { formResponse } = useFormResponse();
    const ruleContext = useDateRuleContext();
    // A date that breaks a rule (e.g. the date it is compared with changed
    // afterwards) shows why right away; Continue/Submit is blocked too.
    const ruleError = isBuilder ? undefined : getDateRuleError(field, ruleContext);
    const flagged = (formResponse.invalidFields?.[field.id] ?? []).includes('DATE_RULE');
    const errorMessage = ruleError ?? (flagged ? '' : undefined);

    return isBuilder ? (
        <DateFieldSection field={field} slide={slide} isBuilder={isBuilder} />
    ) : (
        <QuestionWrapper field={field} errorMessage={errorMessage}>
            <div onSubmit={(e) => e.preventDefault()}>
                <DateFieldSection field={field} slide={slide} isBuilder={isBuilder} />
            </div>
        </QuestionWrapper>
    );
};
export default DateField;
