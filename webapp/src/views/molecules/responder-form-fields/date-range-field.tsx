import { useState } from 'react';

import { format } from 'date-fns';
import { nl as dutch } from 'date-fns/locale/nl';
import { CalendarIcon } from 'lucide-react';

import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { rawDateRange } from '@app/utils/date-range';
import { DateRuleContext, getDateRuleError, getDisabledDayMatcher, isoToLocalDate, resolveDateRuleBounds, toIsoDate } from '@app/utils/date-rules';
import { READ_ONLY_EMPTY } from '@app/utils/form-utils';
import { inputTextOf } from '@app/views/molecules/theme/theme-root';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import { useDateRuleContext } from './date-field';
import { joinIds, useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';
import { ThemedCalendar } from './themed-calendar';

interface IDateRangeField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

type End = 'start' | 'end';

/** The two days as stored (a day that is not a real date is shown as nothing, never rewritten). */
function storedDays(answer: any): { start: string; end: string } {
    const value = rawDateRange(answer);
    return { start: typeof value?.start === 'string' ? value.start : '', end: typeof value?.end === 'string' ? value.end : '' };
}

/** Is the end before the start (both real days)? Compared as text: YYYY-MM-DD sorts as the days do. */
export function rangeEndsBeforeStart(start: string, end: string): boolean {
    return !!isoToLocalDate(start) && !!isoToLocalDate(end) && end < start;
}

/**
 * A date range question: two date pickers, "Start" and "End", in one group
 * named by the question. Each opens the same calendar a date question has
 * (days the question's date rules rule out cannot be picked, and the end
 * cannot be picked before the start). Both are needed once one is chosen: the
 * page asks for the missing one on Continue. The answer is
 * `{ start, end }` in YYYY-MM-DD; an end before the start is said right away.
 */
function DateRangeFieldSection({ field, isBuilder, ruleContext }: IDateRangeField & { ruleContext: DateRuleContext }) {
    const { theme } = useFormState();
    const { formResponse, addFieldDateRangeAnswer, removeAnswer } = useFormResponse();
    const { t, language } = useRespondentLanguage();
    const locale = language === 'nl' ? dutch : undefined;
    const [open, setOpen] = useState<End | null>(null);
    const stored = storedDays(formResponse.answers?.[field.id]);
    const { label: question, group } = useQuestionLabel();
    const readOnly = !!question?.readOnly;
    // Date rules apply to each end, with the other questions as they are now.
    const disabledDays = isBuilder ? undefined : getDisabledDayMatcher(field, ruleContext);
    const firstBound = isBuilder ? undefined : resolveDateRuleBounds(field, ruleContext).find((b) => b.rule.target === 'field' || b.rule.target === 'date')?.bound;

    const save = (start: string, end: string) => {
        if (!start && !end) removeAnswer(field.id);
        else addFieldDateRangeAnswer(field.id, start, end);
    };

    const endPicker = (part: End) => {
        const day = stored[part];
        const date = day ? isoToLocalDate(day) : undefined;
        const buttonId = `date-range-${part}-${field.id}`;
        const labelId = `${buttonId}-label`;
        const valueId = `${buttonId}-value`;
        const otherStart = part === 'end' && stored.start ? isoToLocalDate(stored.start) : undefined;
        // The end cannot be picked before the start; the calendars open on the month of what they relate to.
        const disabled = (candidate: Date) => !!disabledDays?.(candidate) || (!!otherStart && toIsoDate(candidate) < toIsoDate(otherStart));
        const defaultMonth = date ?? otherStart ?? (stored.end && part === 'start' ? isoToLocalDate(stored.end) : undefined) ?? (firstBound ? isoToLocalDate(firstBound) : undefined);
        return (
            <div className="flex min-w-0 flex-1 flex-col gap-1" key={part}>
                <label id={labelId} htmlFor={buttonId} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {t(`DATE_RANGE.${part.toUpperCase()}`)}
                </label>
                <Popover open={open === part} onOpenChange={(next) => setOpen(next ? part : null)}>
                    <PopoverTrigger asChild disabled={isBuilder}>
                        <button
                            id={buttonId}
                            type="button"
                            aria-labelledby={labelId}
                            aria-describedby={joinIds(valueId, question?.errorId)}
                            {...(readOnly ? { role: 'combobox', 'aria-readonly': true } : {})}
                            className={cn('flex min-h-12 w-full cursor-pointer items-center gap-2 border bg-white px-4 py-3 text-base transition duration-150 hover:border-(--hover-border)! lg:text-lg', isBuilder && 'pointer-events-none')}
                            style={{
                                ['--hover-border' as string]: theme?.primary ?? '#101828',
                                borderRadius: styleTokens(theme?.style).fieldRadius,
                                borderColor: theme?.tertiary ?? '#818CA0',
                                color: date ? inputTextOf(theme) : '#667085'
                            }}
                        >
                            <CalendarIcon aria-hidden="true" className="h-6 w-6 shrink-0" style={{ color: theme?.secondary }} />
                            {date ? (
                                <span id={valueId} style={{ color: inputTextOf(theme) }}>
                                    {format(date, 'PPP', { locale })}
                                </span>
                            ) : (
                                <span id={valueId} style={{ color: '#667085' }}>
                                    {readOnly ? <span aria-hidden="true">{READ_ONLY_EMPTY}</span> : t('DATE.PICK')}
                                </span>
                            )}
                        </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start" aria-labelledby={labelId}>
                        <ThemedCalendar
                            mode="single"
                            locale={locale}
                            selected={date}
                            onSelect={(selected: Date | undefined) => {
                                if (!selected) return;
                                const picked = toIsoDate(selected);
                                save(part === 'start' ? picked : stored.start, part === 'end' ? picked : stored.end);
                                setOpen(null);
                            }}
                            disabled={disabled}
                            defaultMonth={defaultMonth}
                            autoFocus
                        />
                    </PopoverContent>
                </Popover>
            </div>
        );
    };

    return (
        <div role="group" aria-labelledby={group['aria-labelledby']} aria-describedby={group['aria-describedby']} className="flex flex-col gap-2 sm:flex-row sm:gap-3">
            {endPicker('start')}
            {endPicker('end')}
        </div>
    );
}

/** The message under a range right now: its end before its start, else what a date rule says of an end. */
export function dateRangeError(field: StandardFormFieldDto, ruleContext: DateRuleContext, t: (key: string) => string, answerId: string = field.id): string | undefined {
    const { start, end } = storedDays(ruleContext.answers?.[answerId]);
    if (rangeEndsBeforeStart(start, end)) return t('RULE.RANGE_ORDER');
    return getDateRuleError(field, ruleContext, answerId);
}

const DateRangeField = ({ field, slide, isBuilder = false }: IDateRangeField) => {
    const ruleContext = useDateRuleContext();
    const { t } = useRespondentLanguage();
    const locked = useFieldRuleStates().isLocked(field.id);
    // An end before the start, or a day a date rule rules out, shows why right away (not for a range the form sets or locks).
    const error = isBuilder || locked ? undefined : dateRangeError(field, ruleContext, t as any);
    return isBuilder ? (
        <DateRangeFieldSection field={field} slide={slide} isBuilder ruleContext={ruleContext} />
    ) : (
        <QuestionWrapper field={field} errorMessage={error}>
            <DateRangeFieldSection field={field} slide={slide} ruleContext={ruleContext} />
        </QuestionWrapper>
    );
};

export default DateRangeField;
