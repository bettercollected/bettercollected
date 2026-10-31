import { useEffect, useState } from 'react';

import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { questionCurrencies } from '@app/utils/answer-rules';
import { currencyDecimals } from '@app/utils/currency';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import { useEnterToNextQuestion } from './next-question';
import { useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface ICurrencyField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

/** The amount as typed, with a comma or a dot for the cents, as a stored plain decimal ("12,5" is "12.5"). */
const storedAmount = (typed: string): string => typed.trim().replace(',', '.');

/** A stored amount as shown to the respondent: the decimal separator of their language. */
const shownAmount = (amount: string, language: string): string => (language === 'nl' ? amount.replace('.', ',') : amount);

/**
 * A currency question: the currency (a choice when the question offers more
 * than one, plain text when it offers one) and the amount. The amount is a
 * text box with the decimal keypad on a phone, read as the respondent writes
 * it (a comma or a dot for the cents, no thousands separator) and stored as a
 * plain decimal with its currency code ("12.50"). What is typed is stored as
 * typed, so a mistake is flagged on Continue where it can be fixed.
 */
function CurrencyFieldSection({ field, isBuilder }: ICurrencyField) {
    const { theme } = useFormState();
    const { formResponse, addFieldCurrencyAnswer, removeAnswer } = useFormResponse();
    const { t, language } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    const locked = useFieldRuleStates().isLocked(field.id);
    const currencies = questionCurrencies(field);
    const stored = formResponse.answers?.[field.id]?.currency;
    const storedCode = typeof stored?.code === 'string' && stored.code ? stored.code : undefined;
    const storedText = typeof stored?.amount === 'string' ? stored.amount : '';
    // The code is remembered while no amount is typed yet: only an amount makes an answer.
    const [code, setCode] = useState(storedCode ?? currencies[0]);
    const [text, setText] = useState(shownAmount(storedText, language));
    const amountId = `input-field-${field.id}`;
    const codeId = `currency-code-${field.id}`;
    const hintId = `currency-hint-${field.id}`;
    const { control } = useQuestionLabel(hintId);

    // Another answer arrives (a rule set it, the form was reset): show it, but never rewrite what is being typed.
    useEffect(() => {
        if (storedCode) setCode(storedCode);
        setText((current) => (storedAmount(current) === storedText ? current : shownAmount(storedText, language)));
    }, [storedCode, storedText, language]);

    const save = (nextCode: string, nextText: string) => {
        const amount = storedAmount(nextText);
        if (amount) addFieldCurrencyAnswer(field.id, nextCode, amount);
        else removeAnswer(field.id);
    };

    const placeholder = currencyDecimals(code) === 0 ? '1250' : t('CURRENCY.PLACEHOLDER');
    const fieldRadius = styleTokens(theme?.style).fieldRadius;

    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-stretch gap-2">
                {currencies.length > 1 ? (
                    <>
                        <label htmlFor={codeId} className="sr-only">
                            {t('CURRENCY.CODE')}
                        </label>
                        <select
                            id={codeId}
                            value={code}
                            disabled={isBuilder || locked}
                            className="min-h-12 min-w-24 shrink-0 border bg-white px-3 text-base lg:text-lg"
                            style={{ borderRadius: fieldRadius, borderColor: theme?.tertiary ?? '#818CA0', color: theme?.primary }}
                            onChange={(event) => {
                                setCode(event.target.value);
                                save(event.target.value, text);
                            }}
                        >
                            {currencies.map((option) => (
                                <option key={option} value={option}>
                                    {option}
                                </option>
                            ))}
                        </select>
                    </>
                ) : (
                    <span className="flex min-h-12 shrink-0 items-center border bg-white px-3 text-base lg:text-lg" style={{ borderRadius: fieldRadius, borderColor: theme?.tertiary ?? '#818CA0', color: theme?.primary }} aria-hidden="true">
                        {code}
                    </span>
                )}
                <FieldInput
                    {...control}
                    id={amountId}
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder={placeholder}
                    value={text}
                    disabled={isBuilder}
                    $formTheme={theme}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
                        setText(event.target.value);
                        save(code, event.target.value);
                    }}
                    onKeyDown={onKeyDown}
                    className="min-h-12 min-w-0 flex-1"
                />
            </div>
            <span id={hintId} className="text-sm text-[#667085]">
                {currencies.length > 1 ? t('CURRENCY.ONE_OF') : t('CURRENCY.IN', { code })}
            </span>
        </div>
    );
}

const CurrencyField = ({ field, slide, isBuilder = false }: ICurrencyField) =>
    isBuilder ? (
        <CurrencyFieldSection field={field} slide={slide} isBuilder />
    ) : (
        <QuestionWrapper field={field}>
            <CurrencyFieldSection field={field} slide={slide} />
        </QuestionWrapper>
    );

export default CurrencyField;
