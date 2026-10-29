'use client';

import { useEffect, useId, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { IFormFieldValidation } from '@app/models/types/form-builder-shared';
import { useAppSelector } from '@app/store/hooks';
import { useCheckAnswerPatternMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { FORMAT_PRESETS, INTEGER_PATTERN, PATTERN_MAX_LENGTH, answerRuleConflicts, answerRuleKind, presetForPattern, summarizeAnswerRules } from '@app/utils/answer-rules';
import { NumberSetting, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';

type Patch = Partial<IFormFieldValidation>;

/** Quiet time after typing in the pattern box before it is checked. */
export const PATTERN_CHECK_DELAY_MS = 400;

/**
 * "Answer rules": limits on an answer beyond Required, written to the
 * field's validations (utils/answer-rules.ts) and checked on the respondent
 * page before Continue/Submit.
 */
export default function AnswerRulesSettings({ field, onChange }: { field: StandardFormFieldDto; onChange: (patch: Patch) => void }) {
    const kind = answerRuleKind(field);
    const rules = field.validations ?? {};
    const summary = summarizeAnswerRules(field);
    const conflicts = answerRuleConflicts(rules);
    const summaryId = useId();
    const valueConflict = rules.minValue !== undefined && rules.maxValue !== undefined && rules.minValue > rules.maxValue;
    if (!kind) return null;

    return (
        <div className="flex flex-col gap-3">
            {kind === 'text' && <TextRules rules={rules} onChange={onChange} />}
            {kind === 'number' && (
                <>
                    <div className="flex gap-2">
                        <NumberSetting label="Lowest" integer={false} step="any" value={rules.minValue} onChange={(minValue) => onChange({ minValue })} invalid={valueConflict} />
                        <NumberSetting label="Highest" integer={false} step="any" value={rules.maxValue} onChange={(maxValue) => onChange({ maxValue })} invalid={valueConflict} />
                    </div>
                    {rules.regex && rules.regex !== INTEGER_PATTERN ? (
                        <p className="text-[11px] leading-relaxed text-black-600">This question has a custom pattern from an import; the server checks it when the answer is sent.</p>
                    ) : (
                        <SettingSwitch label="Whole numbers only" checked={rules.regex === INTEGER_PATTERN} onCheckedChange={(checked) => onChange({ regex: checked ? INTEGER_PATTERN : undefined })} />
                    )}
                </>
            )}
            {kind === 'choices' && (
                <div className="flex gap-2">
                    <NumberSetting label="Pick at least" min={1} max={field.properties?.choices?.length} value={rules.minChoices} onChange={(minChoices) => onChange({ minChoices: minChoices !== undefined ? Math.max(1, minChoices) : undefined })} />
                    <NumberSetting label="Pick at most" min={1} max={field.properties?.choices?.length} value={rules.maxChoices} onChange={(maxChoices) => onChange({ maxChoices: maxChoices !== undefined ? Math.max(1, maxChoices) : undefined })} />
                </div>
            )}

            {conflicts.length > 0 && (
                <ul role="status" className="flex flex-col gap-1 text-[11px] leading-relaxed text-amber-700">
                    {conflicts.map((conflict) => (
                        <li key={conflict}>{conflict}</li>
                    ))}
                </ul>
            )}
            <div id={summaryId} aria-live="polite" className="rounded border border-black-300 bg-black-100 px-3 py-2 text-[11px] leading-relaxed">
                {summary.length ? (
                    <ul className="flex flex-col gap-0.5 text-black-700" aria-label="Active answer rules">
                        {summary.map((line) => (
                            <li key={line}>{line}</li>
                        ))}
                    </ul>
                ) : (
                    <span className="text-black-600">No rules: any answer is accepted.</span>
                )}
            </div>
        </div>
    );
}

function TextRules({ rules, onChange }: { rules: IFormFieldValidation; onChange: (patch: Patch) => void }) {
    const formatId = useId();
    const patternId = useId();
    const preset = presetForPattern(rules.regex);
    const isCustom = !!rules.regex && !preset;
    const [advancedOpen, setAdvancedOpen] = useState(isCustom);
    const [pattern, setPattern] = useState(isCustom ? (rules.regex ?? '') : '');
    // A custom pattern set elsewhere (undo, an import) shows in the box.
    const [shownRegex, setShownRegex] = useState(rules.regex);
    if (shownRegex !== rules.regex) {
        setShownRegex(rules.regex);
        if (isCustom) setPattern(rules.regex ?? '');
    }

    // A custom pattern is checked by the server (RE2 syntax) while it is typed.
    // Only a pattern that passes goes into the form; until then the one the
    // form already has stays, and the reason is shown.
    const { t } = useTranslation('builder');
    const workspace = useAppSelector(selectWorkspace);
    const [checkPattern] = useCheckAnswerPatternMutation();
    const [problem, setProblem] = useState<string | null>(null);
    const [checking, setChecking] = useState(false);
    const latest = useRef(0);
    const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    useEffect(() => () => clearTimeout(timer.current), []);
    const typed = (next: string) => {
        setPattern(next);
        clearTimeout(timer.current);
        const turn = ++latest.current;
        if (!next) {
            setProblem(null);
            setChecking(false);
            onChange({ regex: undefined }); // emptying the box is the way to remove it
            return;
        }
        setChecking(true);
        timer.current = setTimeout(async () => {
            const response: any = await checkPattern({ workspaceId: workspace?.id as string, pattern: next });
            if (turn !== latest.current) return; // typed on since
            setChecking(false);
            if (response?.data?.valid) {
                setProblem(null);
                onChange({ regex: next });
            } else {
                setProblem(response?.data ? (response.data.reason ?? '') : '');
            }
        }, PATTERN_CHECK_DELAY_MS);
    };

    const lengthConflict = rules.minLength !== undefined && rules.maxLength !== undefined && rules.minLength > rules.maxLength;

    return (
        <>
            <div className="flex gap-2">
                <NumberSetting label="Min. characters" min={0} value={rules.minLength} onChange={(minLength) => onChange({ minLength: minLength !== undefined ? Math.max(0, minLength) : undefined })} invalid={lengthConflict} />
                <NumberSetting label="Max. characters" min={1} value={rules.maxLength} onChange={(maxLength) => onChange({ maxLength: maxLength !== undefined ? Math.max(1, maxLength) : undefined })} invalid={lengthConflict} />
            </div>
            <div className="flex flex-col gap-1">
                <label htmlFor={formatId} className="text-xs text-black-700">
                    Format
                </label>
                <select
                    id={formatId}
                    value={preset?.id ?? (isCustom ? 'custom' : '')}
                    onChange={(event) => {
                        const value = event.target.value;
                        if (value === 'custom') {
                            setAdvancedOpen(true);
                            if (pattern && !problem && !checking) onChange({ regex: pattern });
                            return;
                        }
                        // another format replaces what was typed: nothing left to check
                        clearTimeout(timer.current);
                        latest.current++;
                        setProblem(null);
                        setChecking(false);
                        onChange({ regex: FORMAT_PRESETS.find((p) => p.id === value)?.pattern });
                    }}
                    className="h-8 w-full rounded border border-control bg-white px-2 py-0 text-xs focus:border-brand-500"
                >
                    <option value="">Any text</option>
                    {FORMAT_PRESETS.map((p) => (
                        <option key={p.id} value={p.id}>
                            {p.label} (e.g. {p.example})
                        </option>
                    ))}
                    <option value="custom">Custom pattern</option>
                </select>
            </div>
            <details open={advancedOpen} onToggle={(event) => setAdvancedOpen((event.currentTarget as HTMLDetailsElement).open)} className="group">
                <summary className="w-fit cursor-pointer text-xs font-medium text-black-600 hover:text-black-900">Advanced: custom pattern</summary>
                <div className="mt-2 flex flex-col gap-1">
                    <label htmlFor={patternId} className="text-xs text-black-700">
                        Regular expression
                    </label>
                    <input
                        id={patternId}
                        type="text"
                        spellCheck={false}
                        maxLength={PATTERN_MAX_LENGTH}
                        value={pattern}
                        placeholder="^[A-Z]{3}[0-9]{4}$"
                        aria-describedby={problem !== null ? `${patternId}-problem ${patternId}-hint` : `${patternId}-hint`}
                        aria-invalid={problem !== null ? true : undefined}
                        onChange={(event) => typed(event.target.value)}
                        className={`h-8 w-full rounded border bg-white px-2 font-mono text-xs focus:border-brand-500 ${problem !== null ? 'border-red-600' : 'border-control'}`}
                    />
                    {problem !== null && (
                        <p id={`${patternId}-problem`} role="alert" className="text-[11px] leading-relaxed text-red-700">
                            {problem ? t('PATTERN_CHECK.INVALID', { reason: problem }) : t('PATTERN_CHECK.UNAVAILABLE')} {t('PATTERN_CHECK.SYNTAX')}
                            {rules.regex ? ` ${t('PATTERN_CHECK.KEPT')}` : ''}
                        </p>
                    )}
                    <p id={`${patternId}-hint`} className="text-[11px] leading-relaxed text-black-600">
                        Answers must match it (use ^ and $ to match the whole answer). It is checked when the answer is sent, not while it is typed. Respondents see a general “not in the expected format” message, so say in the description what you expect.
                    </p>
                </div>
            </details>
        </>
    );
}
