'use client';

import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from 'react';

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
    formulaText,
    getCalculatedFields,
    localToday,
    parseFormulaText,
    pipedInto,
    questionKeys,
    readingFor,
    sampleVariables,
    unansweredAsZero
} from '@app/utils/calculated-fields';
import { NumberSetting, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';

const STYLE_LABELS: Record<string, string> = { number: 'Number', currency: 'Amount (€)', percent: 'Percentage', text: 'Plain text' };
const MAX_SUGGESTIONS = 8;

/** The `{…` reference the caret is in, if any: where it starts and what is typed so far. */
export function openReference(text: string, caret: number): { start: number; query: string } | null {
    const before = text.slice(0, caret);
    const open = before.lastIndexOf('{');
    if (open < 0 || before.lastIndexOf('}') > open) return null;
    // inside a text literal? count unescaped quotes before the brace
    const quotes = (before.slice(0, open).match(/(^|[^\\])"/g) ?? []).length;
    if (quotes % 2 === 1) return null;
    return { start: open, query: before.slice(open + 1) };
}

export function suggestionsFor(variables: CalculationVariable[], query: string): CalculationVariable[] {
    const q = query.trim().toLowerCase();
    const starts = variables.filter((variable) => variable.label.toLowerCase().startsWith(q));
    const contains = variables.filter((variable) => !starts.includes(variable) && variable.label.toLowerCase().includes(q));
    return [...starts, ...contains].slice(0, MAX_SUGGESTIONS);
}

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

/** An error at the end of the formula: it is probably still being typed. */
export const isIncompleteError = (text: string, error: { start: number }): boolean => error.start >= text.trimEnd().length;

/** How long typing must pause before an unfinished formula's error shows. */
export const FORMULA_IDLE_MS = 800;

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
    const id = useId();
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const variables = useMemo(() => calculationVariables(slides, hiddenNames).filter((variable) => variable.key !== field.id), [slides, hiddenNames, field.id]);
    const expression = field.properties?.expression as ExprNode | undefined;
    const stored = JSON.stringify(expression ?? null);

    const [draft, setDraft] = useState(() => formulaText(expression, variables));
    const [error, setError] = useState<{ message: string; start: number; end: number } | null>(null);
    const [settled, setSettled] = useState(true);
    const idle = useRef<number | undefined>(undefined);
    useEffect(() => () => window.clearTimeout(idle.current), []);
    const typing = () => {
        setSettled(false);
        window.clearTimeout(idle.current);
        idle.current = window.setTimeout(() => setSettled(true), FORMULA_IDLE_MS);
    };
    // Another field selected, or the formula changed elsewhere (AI, undo):
    // show it, unless the draft already says the same.
    const [shown, setShown] = useState({ id: field.id, stored });
    if (shown.id !== field.id || shown.stored !== stored) {
        setShown({ id: field.id, stored });
        const parsed = parseFormulaText(draft, variables);
        if (shown.id !== field.id || JSON.stringify(parsed.expression ?? null) !== stored) {
            setDraft(formulaText(expression, variables));
            setError(null);
        }
    }

    const [caret, setCaret] = useState(0);
    const [active, setActive] = useState(0);
    const [dismissed, setDismissed] = useState(false);
    const reference = openReference(draft, caret);
    const suggestions = reference && !dismissed ? suggestionsFor(variables, reference.query) : [];
    const listOpen = suggestions.length > 0;

    const apply = (text: string) => {
        setDraft(text);
        const result = parseFormulaText(text, variables);
        if (result.error) {
            setError(result.error);
            return;
        }
        setError(null);
        onChange('expression', result.expression);
    };

    const choose = (variable: CalculationVariable) => {
        if (!reference) return;
        const label = variable.label.replace(/\\/g, '\\\\').replace(/\}/g, '\\}');
        const after = draft.slice(caret).replace(/^[^{}]*\}/, '');
        const text = `${draft.slice(0, reference.start)}{${label}}${after}`;
        const position = reference.start + label.length + 2;
        apply(text);
        setCaret(position);
        setActive(0);
        window.setTimeout(() => {
            textareaRef.current?.focus();
            textareaRef.current?.setSelectionRange(position, position);
        }, 0);
    };

    const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (!listOpen) return;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            const step = event.key === 'ArrowDown' ? 1 : -1;
            setActive((index) => (index + step + suggestions.length) % suggestions.length);
        } else if (event.key === 'Enter' || event.key === 'Tab') {
            event.preventDefault();
            choose(suggestions[Math.min(active, suggestions.length - 1)]);
        } else if (event.key === 'Escape') {
            event.preventDefault();
            setDismissed(true);
        }
    };

    const problems = calculationProblems(slides, hiddenNames).filter((problem) => problem.fieldId === field.id);
    const format: CalculationFormat = field.properties?.format ?? {};
    const style = format.style ?? 'number';
    const show = (value: ExprValue) => (value === null ? '' : typeof value === 'number' ? formatCalculatedValue(value, format, 'en') : formatExpressionValue(value));
    const previewText = error ? '' : show(previewValue(slides, field, expression, variables));
    // The same with one answer left out: what "unanswered as 0" changes.
    const emptied = error ? undefined : firstQuestionKey(expression, variables, slides);
    const emptiedText = emptied ? show(previewValue(slides, field, expression, variables, emptied.key)) : '';
    const asZero = unansweredAsZero(field);
    const pipedTo = field.properties?.hiddenFromRespondents ? pipedInto(slides, field.id, endings) : [];
    // While the reference list is open, the formula is unfinished on purpose
    // ("missing }"): its error waits until a field is picked or typing goes on.
    // Other errors show at once; an unfinished one ("Expected \",\" or \")\"")
    // waits until typing pauses or the input is left.
    const shownError = listOpen || (error && !settled && isIncompleteError(draft, error)) ? null : error;
    const setFormat = (patch: Partial<CalculationFormat>) => {
        const next = { ...format, ...patch };
        (Object.keys(next) as Array<keyof CalculationFormat>).forEach((key) => next[key] === undefined && delete next[key]);
        onChange('format', Object.keys(next).length ? next : undefined);
    };

    const formulaId = `${id}-formula`;
    const listId = `${id}-suggestions`;
    const helpId = `${id}-help`;
    const errorId = `${id}-error`;

    return (
        <div className="flex w-full flex-col gap-4">
            <div className="flex w-full flex-col gap-1">
                <label htmlFor={formulaId} className="text-xs font-medium text-black-700">
                    Formula
                </label>
                {/* The suggestions open in flow under the input (about five rows, scrolling), pushing the hint and preview down instead of covering them. */}
                <div className="relative">
                    <textarea
                        ref={textareaRef}
                        id={formulaId}
                        value={draft}
                        rows={3}
                        spellCheck={false}
                        placeholder="e.g. round({Price} * {Quantity} * 1.21, 2)"
                        role="combobox"
                        aria-autocomplete="list"
                        aria-expanded={listOpen}
                        aria-controls={listOpen ? listId : undefined}
                        aria-activedescendant={listOpen ? `${listId}-${Math.min(active, suggestions.length - 1)}` : undefined}
                        aria-invalid={!!shownError || problems.length > 0 || undefined}
                        aria-describedby={[shownError || problems.length ? errorId : '', helpId].filter(Boolean).join(' ')}
                        onChange={(event) => {
                            setCaret(event.target.selectionStart ?? event.target.value.length);
                            setDismissed(false);
                            typing();
                            setActive(0);
                            apply(event.target.value);
                        }}
                        onSelect={(event) => setCaret((event.target as HTMLTextAreaElement).selectionStart ?? 0)}
                        onKeyDown={onKeyDown}
                        onBlur={() => {
                            setSettled(true);
                            window.setTimeout(() => setDismissed(true), 150);
                        }}
                        className={`w-full rounded-lg border p-2 font-mono text-xs ${shownError || problems.length ? 'border-[#C43D3D]' : 'border-control focus:border-brand-500'}`}
                    />
                    {listOpen && (
                        <ul id={listId} role="listbox" aria-label="Fields" className="mt-1 max-h-[148px] overflow-auto rounded border border-black-300 bg-white py-1">
                            {suggestions.map((variable, index) => (
                                <li
                                    key={variable.key}
                                    id={`${listId}-${index}`}
                                    role="option"
                                    aria-selected={index === active}
                                    onMouseDown={(event) => event.preventDefault()}
                                    onClick={() => choose(variable)}
                                    onKeyDown={(event) => event.key === 'Enter' && choose(variable)}
                                    className={`flex cursor-pointer items-center justify-between gap-2 px-2 py-1.5 text-xs ${index === active ? 'bg-brand-100 text-brand-600' : 'text-black-800'}`}
                                >
                                    <span className="truncate">{variable.label}</span>
                                    <span className="shrink-0 text-[10px] text-black-600">{variable.kind === 'hidden' ? 'hidden field' : variable.kind === 'calculated' ? 'calculation' : variable.kind === 'group' ? 'each item' : 'answer'}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
                {(shownError || problems.length > 0) && (
                    <p id={errorId} role="alert" className="text-[11px] leading-relaxed text-[#C43D3D]">
                        {shownError ? (
                            <>
                                {shownError.message} <span className="text-black-600">(at character {shownError.start + 1})</span>
                                {draft && (
                                    <code className="mt-1 block font-mono break-all whitespace-pre-wrap text-black-800">
                                        {draft.slice(0, shownError.start)}
                                        <mark className="rounded-sm bg-[#FDE8E8] text-[#C43D3D] underline">{draft.slice(shownError.start, Math.max(shownError.end, shownError.start + 1)) || ' '}</mark>
                                        {draft.slice(Math.max(shownError.end, shownError.start + 1))}
                                    </code>
                                )}
                            </>
                        ) : (
                            problems[0].message
                        )}
                    </p>
                )}
                <p id={helpId} className="text-[11px] leading-relaxed text-black-600">
                    Type {'{'} to pick a question. Use + − * / and functions like sum, round, if, min, max.
                </p>
            </div>

            <div className="flex flex-col gap-1 rounded-lg bg-black-100 px-3 py-2">
                <span className="text-[11px] text-black-600">Preview with sample answers</span>
                <span className="text-sm font-semibold text-black-800 tabular-nums" data-testid="calculation-preview">
                    {previewText || '—'}
                </span>
                {emptied && (
                    <span className="text-[11px] text-black-600" data-testid="calculation-preview-empty">
                        Without an answer to {emptied.label}: <span className="font-semibold text-black-800 tabular-nums">{emptiedText || 'no value'}</span>
                    </span>
                )}
            </div>

            <div className="flex w-full flex-col gap-1">
                <label htmlFor={`${id}-style`} className="text-xs text-black-700">
                    Show as
                </label>
                <select
                    id={`${id}-style`}
                    value={style}
                    onChange={(event) => setFormat({ style: event.target.value as CalculationFormat['style'], currency: event.target.value === 'currency' ? (format.currency ?? DEFAULT_CURRENCY) : undefined })}
                    className="h-8 rounded border border-control px-2 py-0 text-xs"
                >
                    {CALCULATION_STYLES.map((option) => (
                        <option key={option} value={option}>
                            {STYLE_LABELS[option]}
                        </option>
                    ))}
                </select>
                {style === 'percent' && <p className="text-[11px] leading-relaxed text-black-600">0.25 shows as 25%.</p>}
            </div>
            {style !== 'text' && (
                <NumberSetting
                    label="Decimals"
                    value={format.decimals}
                    min={0}
                    max={CALCULATION_MAX_DECIMALS}
                    placeholder={style === 'currency' ? '2' : style === 'percent' ? '0' : 'As computed'}
                    onChange={(value) => setFormat({ decimals: value === undefined ? undefined : Math.min(CALCULATION_MAX_DECIMALS, Math.max(0, Math.round(value))) })}
                />
            )}
            <SettingSwitch
                label="Treat unanswered as 0"
                checked={asZero}
                onCheckedChange={(checked) => onChange('unansweredAsZero', checked)}
                hint={asZero ? 'A question left empty counts as 0, so one empty optional answer does not blank the result.' : 'The result stays empty until every question it uses is answered.'}
            />
            <SettingSwitch
                label="Hide from respondents"
                checked={!!field.properties?.hiddenFromRespondents}
                onCheckedChange={(checked) => onChange('hiddenFromRespondents', checked || undefined)}
                hint={field.properties?.hiddenFromRespondents ? 'Computed and stored with each response; respondents never see it. The formula is part of the form page, so it is not a secret.' : 'Respondents see the value update as they answer.'}
            />
            {field.properties?.hiddenFromRespondents && pipedTo.length > 0 && (
                <p role="status" className="text-[11px] leading-relaxed text-amber-700" data-testid="hidden-piped-warning">
                    This value is piped into {pipedTo.join(', ')}, so respondents would see it there. Remove it from that text, or show the calculation.
                </p>
            )}
        </div>
    );
}
