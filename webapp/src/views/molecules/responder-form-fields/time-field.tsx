import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { isTime } from '@app/utils/time-of-day';

import { useEnterToNextQuestion } from './next-question';
import { joinIds, useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface ITimeField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

/**
 * The window a time question allows, as a sentence ("From 09:00 to 17:30"),
 * or undefined when it has none.
 */
export function timeWindowText(field: StandardFormFieldDto, t: (key: string, options?: Record<string, unknown>) => string): string | undefined {
    const min = isTime(field.properties?.minTime) ? field.properties?.minTime : undefined;
    const max = isTime(field.properties?.maxTime) ? field.properties?.maxTime : undefined;
    if (min && max) return t('TIME.RANGE', { min, max });
    if (min) return t('TIME.FROM', { min });
    if (max) return t('TIME.UNTIL', { max });
    return undefined;
}

/**
 * A time question: the browser's own time input (its picker is the best one
 * on a phone, and it shows the time the way the person's device is set to,
 * 24-hour in the Netherlands). The answer is always "HH:MM". Named by the
 * question; the allowed window is read out as part of its description.
 */
function TimeFieldSection({ field, isBuilder }: ITimeField) {
    const { theme } = useFormState();
    const { formResponse, addFieldTimeAnswer, removeAnswer } = useFormResponse();
    const { t, language } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    const locked = useFieldRuleStates().isLocked(field.id);
    const id = `input-field-${field.id}`;
    const hintId = `time-hint-${field.id}`;
    const label = field.properties?.label?.trim();
    const labelId = `time-label-${field.id}`;
    const stored = formResponse.answers?.[field.id]?.time;
    const value = typeof stored === 'string' ? stored : '';
    const windowText = timeWindowText(field, t);
    const { label: question, control } = useQuestionLabel(windowText && hintId);
    // Named by the question (and the field's own label); the allowed window describes it.
    const labelledBy = question?.labelledBy ? joinIds(question.labelledBy, label && labelId) : undefined;

    return (
        <div className="flex flex-col gap-1">
            {label && (
                <label id={labelId} htmlFor={id} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {label}
                </label>
            )}
            <FieldInput
                {...control}
                id={id}
                type="time"
                step={60}
                lang={language}
                min={field.properties?.minTime}
                max={field.properties?.maxTime}
                value={value}
                disabled={isBuilder}
                // A field rule that locks the question sets its value: it shows, and cannot be changed.
                readOnly={locked}
                aria-labelledby={labelledBy}
                aria-label={labelledBy || label ? undefined : t('TIME.PICK')}
                $formTheme={theme}
                // The native control reports "" until the time is complete: that is no answer.
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
                    if (locked) return;
                    if (event.target.value) addFieldTimeAnswer(field.id, event.target.value);
                    else removeAnswer(field.id);
                }}
                onKeyDown={onKeyDown}
                className="min-h-12 max-w-xs"
            />
            {windowText && (
                <span id={hintId} className="text-sm text-[#667085]">
                    {windowText}
                </span>
            )}
        </div>
    );
}

const TimeField = ({ field, slide, isBuilder = false }: ITimeField) =>
    isBuilder ? (
        <TimeFieldSection field={field} slide={slide} isBuilder={isBuilder} />
    ) : (
        <QuestionWrapper field={field}>
            <TimeFieldSection field={field} slide={slide} isBuilder={isBuilder} />
        </QuestionWrapper>
    );

export default TimeField;
