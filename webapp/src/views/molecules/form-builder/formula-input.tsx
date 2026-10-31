'use client';

import { KeyboardEvent, useEffect, useId, useRef, useState } from 'react';

import { CalculationVariable, formulaText, parseFormulaText } from '@app/utils/calculated-fields';

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

export const isIncompleteError = (text: string, error: { start: number }): boolean => error.start >= text.trimEnd().length;

/** How long typing must pause before an unfinished formula's error is shown. */
export const FORMULA_IDLE_MS = 800;

export interface FormulaError {
    message: string;
    start: number;
    end: number;
}

/** The kind labels of the reference list ("answer", "calculation", ...), as the builder shows them. */
const KIND_LABELS: Record<CalculationVariable['kind'], string> = { field: 'answer', calculated: 'calculation', group: 'each item', hidden: 'hidden field' };

/**
 * A formula box: the expression written as text (`{Field}` references with
 * autocomplete), parsed as it is typed. A formula that parses goes out
 * through `onExpression`; one that does not stays a draft with its error shown
 * at its position, and the formula the form already has stays. Shared by a
 * calculated question's formula and a field rule's formula.
 */
export default function FormulaInput({
    label,
    resetKey,
    expression,
    variables,
    onExpression,
    onError,
    problem,
    placeholder,
    help,
    rows = 3,
    invalid
}: {
    label: string;
    /** Another question or rule selected: show its formula. */
    resetKey: string;
    /** The formula the form has (an expressions-v1 AST). */
    expression: unknown;
    variables: CalculationVariable[];
    onExpression: (expression: ReturnType<typeof parseFormulaText>['expression']) => void;
    /** The parse error of the draft (null: none), for what depends on it. */
    onError?: (error: FormulaError | null) => void;
    /** A problem with the formula that is not a parse error (a unknown reference), shown below the box. */
    problem?: string;
    placeholder?: string;
    help?: string;
    rows?: number;
    invalid?: boolean;
}) {
    const id = useId();
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const stored = JSON.stringify(expression ?? null);

    const [draft, setDraft] = useState(() => formulaText(expression, variables));
    const [error, setErrorState] = useState<FormulaError | null>(null);
    const setError = (next: FormulaError | null) => {
        setErrorState(next);
        onError?.(next);
    };
    const [settled, setSettled] = useState(true);
    const idle = useRef<number | undefined>(undefined);
    useEffect(() => () => window.clearTimeout(idle.current), []);
    const typing = () => {
        setSettled(false);
        window.clearTimeout(idle.current);
        idle.current = window.setTimeout(() => setSettled(true), FORMULA_IDLE_MS);
    };
    // Another formula selected, or the formula changed elsewhere (AI, undo):
    // show it, unless the draft already says the same.
    const [shown, setShown] = useState({ id: resetKey, stored });
    if (shown.id !== resetKey || shown.stored !== stored) {
        setShown({ id: resetKey, stored });
        const parsed = parseFormulaText(draft, variables);
        if (shown.id !== resetKey || JSON.stringify(parsed.expression ?? null) !== stored) {
            setDraft(formulaText(expression, variables));
            setErrorState(null);
            onError?.(null);
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
        onExpression(result.expression);
    };

    const choose = (variable: CalculationVariable) => {
        if (!reference) return;
        const name = variable.label.replace(/\\/g, '\\\\').replace(/\}/g, '\\}');
        const after = draft.slice(caret).replace(/^[^{}]*\}/, '');
        const text = `${draft.slice(0, reference.start)}{${name}}${after}`;
        const position = reference.start + name.length + 2;
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

    // While the reference list is open, the formula is unfinished on purpose
    // ("missing }"): its error waits until a field is picked or typing goes on.
    // Other errors show at once; an unfinished one ("Expected \",\" or \")\"")
    // waits until typing pauses or the input is left.
    const shownError = listOpen || (error && !settled && isIncompleteError(draft, error)) ? null : error;
    const formulaId = `${id}-formula`;
    const listId = `${id}-suggestions`;
    const helpId = `${id}-help`;
    const errorId = `${id}-error`;
    const bad = !!shownError || !!problem || !!invalid;

    return (
        <div className="flex w-full flex-col gap-1">
            <label htmlFor={formulaId} className="text-xs font-medium text-black-700">
                {label}
            </label>
            {/* The suggestions open in flow under the input (about five rows, scrolling), pushing the hint and preview down instead of covering them. */}
            <div className="relative">
                <textarea
                    ref={textareaRef}
                    id={formulaId}
                    value={draft}
                    rows={rows}
                    spellCheck={false}
                    placeholder={placeholder}
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded={listOpen}
                    aria-controls={listOpen ? listId : undefined}
                    aria-activedescendant={listOpen ? `${listId}-${Math.min(active, suggestions.length - 1)}` : undefined}
                    aria-invalid={bad || undefined}
                    aria-describedby={[shownError || problem ? errorId : '', help ? helpId : ''].filter(Boolean).join(' ') || undefined}
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
                    className={`w-full rounded-lg border p-2 font-mono text-xs ${bad ? 'border-[#C43D3D]' : 'border-control focus:border-brand-500'}`}
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
                                <span className="shrink-0 text-[10px] text-black-600">{KIND_LABELS[variable.kind]}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
            {(shownError || problem) && (
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
                        problem
                    )}
                </p>
            )}
            {help && (
                <p id={helpId} className="text-[11px] leading-relaxed text-black-600">
                    {help}
                </p>
            )}
        </div>
    );
}
