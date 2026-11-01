'use client';

import { useId, useMemo, useState } from 'react';

import { useTranslation } from 'react-i18next';
import { ExprNode, ExprValue, evaluateExpression, formatExpressionValue } from '@app/lib/expressions';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import {
    CALCULATION_MAX_DECIMALS,
    CALCULATION_STYLES,
    CalculationFormat,
    CalculationVariable,
    DEFAULT_CURRENCY,
    calculationProblems,
    calculationVariables,
    evaluationOrder,
    expressionVariables,
    formatCalculatedValue,
    getCalculatedFields,
    localToday,
    pipedInto,
    questionKeys,
    readingFor,
    sampleVariables,
    unansweredAsZero
} from '@app/utils/calculated-fields';
import FormulaInput, { FORMULA_IDLE_MS, FormulaError, isIncompleteError, openReference, suggestionsFor } from '@app/views/molecules/form-builder/formula-input';
import { NumberSetting, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';

// The formula box moved to formula-input.tsx; its helpers are still imported from here.
export { FORMULA_IDLE_MS, isIncompleteError, openReference, suggestionsFor };

/** The value a formula gives with sample answers (other calculations computed first). */
export function previewValue(slides: StandardFormFieldDto[], field: StandardFormFieldDto, expression: ExprNode | undefined, variables: CalculationVariable[], emptyKey?: string): ExprValue {
    if (expression === undefined) return null;
    const values: Record<string, unknown> = sampleVariables(variables, slides);
    if (emptyKey) values[emptyKey] = null;
    const questions = questionKeys(slides);
    const context = { today: localToday() };
    const others = evaluationOrder(getCalculatedFields(slides).filter((calc) => calc.id !== field.id));
    others.forEach((calc) => {
        try {
            values[calc.id] = calc.properties?.expression == null ? null : evaluateExpression(calc.properties.expression, readingFor(calc, values, questions), context);
        } catch {
            values[calc.id] = null;
        }
    });
    try {
        return evaluateExpression(expression, readingFor({ ...field, properties: { ...field.properties, expression } }, values, questions), context);
    } catch {
        return null;
    }
}

/** The first question (not a calculation) a formula reads: the one the preview leaves unanswered. */
export function firstQuestionKey(expression: unknown, variables: CalculationVariable[], slides: StandardFormFieldDto[] = []): CalculationVariable | undefined {
    // Through other calculations too: the first answered question the
    // dependency chain reaches.
    const formulas = new Map(getCalculatedFields(slides).map((calc) => [calc.id, calc.properties?.expression]));
    const byKey = new Map(variables.map((variable) => [variable.key, variable]));
    const seen = new Set<string>();
    const pending = [...expressionVariables(expression)];
    while (pending.length) {
        const key = pending.shift()!;
        if (seen.has(key)) continue;
        seen.add(key);
        const variable = byKey.get(key);
        if (variable?.kind === 'field') return variable;
        if (formulas.has(key)) pending.push(...expressionVariables(formulas.get(key)));
    }
    return undefined;
}

/**
 * The inspector's Calculation settings: the formula (with `{Field}`
 * autocomplete and inline errors at their position), a live preview with
 * sample answers, the display format and whether respondents see the value.
 * Changes go out through `onChange(property, value)` (properties.expression,
 * properties.format, properties.hiddenFromRespondents).
 */
export default function CalculatedFieldSettings({
    field,
    slides,
    hiddenNames,
    onChange,
    endings
}: {
    field: StandardFormFieldDto;
    slides: StandardFormFieldDto[];
    hiddenNames: string[];
    /** The form's endings, to find a hidden value piped into them. */
    endings?: Array<{ title?: string; message?: string }>;
    onChange: (property: 'expression' | 'format' | 'hiddenFromRespondents' | 'unansweredAsZero', value: unknown) => void;
}) {
    const { t, i18n } = useTranslation('builder');
    const id = useId();
    const variables = useMemo(() => calculationVariables(slides, hiddenNames).filter((variable) => variable.key !== field.id), [slides, hiddenNames, field.id]);
    const expression = field.properties?.expression as ExprNode | undefined;
    // The formula box's parse error: the preview waits for a formula that parses.
    const [error, setError] = useState<FormulaError | null>(null);

    const problems = calculationProblems(slides, hiddenNames).filter((problem) => problem.fieldId === field.id);
    const format: CalculationFormat = field.properties?.format ?? {};
    const style = format.style ?? 'number';
    const show = (value: ExprValue) => (value === null ? '' : typeof value === 'number' ? formatCalculatedValue(value, format, i18n.language?.startsWith('nl') ? 'nl' : 'en') : formatExpressionValue(value));
    const previewText = error ? '' : show(previewValue(slides, field, expression, variables));
    // The same with one answer left out: what "unanswered as 0" changes.
    const emptied = error ? undefined : firstQuestionKey(expression, variables, slides);
    const emptiedText = emptied ? show(previewValue(slides, field, expression, variables, emptied.key)) : '';
    const asZero = unansweredAsZero(field);
    const pipedTo = field.properties?.hiddenFromRespondents ? pipedInto(slides, field.id, endings) : [];
    const setFormat = (patch: Partial<CalculationFormat>) => {
        const next = { ...format, ...patch };
        (Object.keys(next) as Array<keyof CalculationFormat>).forEach((key) => next[key] === undefined && delete next[key]);
        onChange('format', Object.keys(next).length ? next : undefined);
    };

    return (
        <div className="flex w-full flex-col gap-4">
            <FormulaInput
                label={t('CALC.FORMULA')}
                resetKey={field.id}
                expression={expression}
                variables={variables}
                onExpression={(next) => onChange('expression', next)}
                onError={setError}
                problem={problems[0]?.message}
                placeholder={t('CALC.FORMULA_PLACEHOLDER')}
                help={t('CALC.FORMULA_HELP')}
            />

            <div className="flex flex-col gap-1 rounded-lg bg-black-100 px-3 py-2">
                <span className="text-[11px] text-black-600">{t('CALC.PREVIEW')}</span>
                <span className="text-sm font-semibold text-black-800 tabular-nums" data-testid="calculation-preview">
                    {previewText || '—'}
                </span>
                {emptied && (
                    <span className="text-[11px] text-black-600" data-testid="calculation-preview-empty">
                        {t('CALC.WITHOUT_ANSWER', { label: emptied.label })} <span className="font-semibold text-black-800 tabular-nums">{emptiedText || t('CALC.NO_VALUE')}</span>
                    </span>
                )}
            </div>

            <div className="flex w-full flex-col gap-1">
                <label htmlFor={`${id}-style`} className="text-xs text-black-700">
                    {t('CALC.SHOW_AS')}
                </label>
                <select
                    id={`${id}-style`}
                    value={style}
                    onChange={(event) => setFormat({ style: event.target.value as CalculationFormat['style'], currency: event.target.value === 'currency' ? (format.currency ?? DEFAULT_CURRENCY) : undefined })}
                    className="h-8 rounded border border-control px-2 py-0 text-xs"
                >
                    {CALCULATION_STYLES.map((option) => (
                        <option key={option} value={option}>
                            {t(`CALC.STYLE_${option}`)}
                        </option>
                    ))}
                </select>
                {style === 'percent' && <p className="text-[11px] leading-relaxed text-black-600">{t('CALC.PERCENT_HINT')}</p>}
            </div>
            {style !== 'text' && (
                <NumberSetting
                    label={t('CALC.DECIMALS')}
                    value={format.decimals}
                    min={0}
                    max={CALCULATION_MAX_DECIMALS}
                    placeholder={style === 'currency' ? '2' : style === 'percent' ? '0' : t('CALC.AS_COMPUTED')}
                    onChange={(value) => setFormat({ decimals: value === undefined ? undefined : Math.min(CALCULATION_MAX_DECIMALS, Math.max(0, Math.round(value))) })}
                />
            )}
            <SettingSwitch
                label={t('CALC.UNANSWERED_ZERO')}
                checked={asZero}
                onCheckedChange={(checked) => onChange('unansweredAsZero', checked)}
                hint={asZero ? t('CALC.UNANSWERED_ZERO_ON') : t('CALC.UNANSWERED_ZERO_OFF')}
            />
            <SettingSwitch
                label={t('CALC.HIDE')}
                checked={!!field.properties?.hiddenFromRespondents}
                onCheckedChange={(checked) => onChange('hiddenFromRespondents', checked || undefined)}
                hint={field.properties?.hiddenFromRespondents ? t('CALC.HIDE_ON') : t('CALC.HIDE_OFF')}
            />
            {field.properties?.hiddenFromRespondents && pipedTo.length > 0 && (
                <p role="status" className="text-[11px] leading-relaxed text-amber-700" data-testid="hidden-piped-warning">
                    {t('CALC.PIPED', { where: pipedTo.join(', ') })}
                </p>
            )}
        </div>
    );
}
