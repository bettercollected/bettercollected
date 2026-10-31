import { useEffect, useState } from 'react';

import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { getDateRuleError } from '@app/utils/date-rules';
import { dayBoxesToIso, isoToDayBoxes } from '@app/utils/day-boxes';

import { useDateRuleContext } from './date-field';
import { useEnterToNextQuestion } from './next-question';
import { joinIds, useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface IDayField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

/**
 * A date typed as three labelled boxes in the order Dutch (and most of
 * Europe) writes it: day, month, year. For dates a calendar is slow for: a
 * birth date, a date years away. The boxes are numeric (the phone shows the
 * number pad), each has its own visible label, and the three are one group
 * named by the question. The answer is the calendar day "YYYY-MM-DD", the
 * same as a date question's, so date rules apply too.
 *
 * Anything typed counts as an answer: a date that does not exist (31 02) or
 * is incomplete is stored as typed, so it is flagged where the respondent can
 * fix it (on Continue) and never silently dropped.
 */
function DayFieldSection({ field, isBuilder }: IDayField) {
    const { theme } = useFormState();
    const { formResponse, addFieldDateAnswer, removeAnswer } = useFormResponse();
    const { t } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    const stored = formResponse.answers?.[field.id]?.date;
    const [boxes, setBoxes] = useState(() => isoToDayBoxes(typeof stored === 'string' ? stored : ''));
    const hintId = `day-hint-${field.id}`;
    const label = field.properties?.label?.trim();
    const labelId = `day-label-${field.id}`;
    const { label: question, group } = useQuestionLabel(hintId);
    const labelledBy = question?.labelledBy ? joinIds(question.labelledBy, label && labelId) : undefined;

    // Another answer arrives (a rule set it, the form was reset): show it, but never
    // rewrite the boxes while the person is typing what they already stored.
    useEffect(() => {
        const next = typeof stored === 'string' ? stored : '';
        setBoxes((current) => (dayBoxesToIso(current) === next ? current : isoToDayBoxes(next)));
    }, [stored]);

    // A field rule that locks the question sets its value: the boxes show it, and cannot be typed over.
    const locked = useFieldRuleStates().isLocked(field.id);

    const change = (part: 'day' | 'month' | 'year') => (event: React.ChangeEvent<HTMLInputElement>) => {
        if (locked) return;
        const next = { ...boxes, [part]: event.target.value.replace(/\D/g, '').slice(0, part === 'year' ? 4 : 2) };
        setBoxes(next);
        const iso = dayBoxesToIso(next);
        if (iso) addFieldDateAnswer(field.id, iso);
        else removeAnswer(field.id);
    };

    const box = (part: 'day' | 'month' | 'year', width: string) => {
        const id = `day-${part}-${field.id}`;
        return (
            <div className={`flex flex-col gap-1 ${width}`}>
                <label htmlFor={id} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {t(`DAY.${part.toUpperCase()}`)}
                </label>
                <FieldInput
                    id={id}
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    pattern="[0-9]*"
                    maxLength={part === 'year' ? 4 : 2}
                    value={boxes[part]}
                    disabled={isBuilder}
                    readOnly={locked}
                    aria-readonly={locked || undefined}
                    aria-describedby={hintId}
                    aria-invalid={question?.invalid || undefined}
                    $formTheme={theme}
                    onChange={change(part)}
                    onKeyDown={onKeyDown}
                    className="min-h-12 text-center"
                />
            </div>
        );
    };

    return (
        <div role="group" {...group} aria-labelledby={labelledBy} className="flex flex-col gap-1">
            {label && (
                <span id={labelId} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {label}
                </span>
            )}
            <div className="flex items-end gap-3">
                {box('day', 'w-20')}
                {box('month', 'w-20')}
                {box('year', 'w-28')}
            </div>
            <span id={hintId} className="text-sm text-[#667085]">
                {t('DAY.EXAMPLE')}
            </span>
        </div>
    );
}

const DayField = ({ field, slide, isBuilder = false }: IDayField) => {
    const ruleContext = useDateRuleContext();
    const locked = useFieldRuleStates().isLocked(field.id);
    // A date that breaks a date rule shows why right away (not for a date the form sets or locks).
    const ruleError = isBuilder || locked ? undefined : getDateRuleError(field, ruleContext);
    return isBuilder ? (
        <DayFieldSection field={field} slide={slide} isBuilder />
    ) : (
        <QuestionWrapper field={field} errorMessage={ruleError}>
            <DayFieldSection field={field} slide={slide} />
        </QuestionWrapper>
    );
};

export default DayField;
