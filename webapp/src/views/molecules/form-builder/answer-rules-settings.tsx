'use client';

import { useId, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { IFormFieldValidation } from '@app/models/types/form-builder-shared';
import { FORMAT_PRESETS, INTEGER_PATTERN, PATTERN_MAX_LENGTH, answerRuleConflicts, answerRuleKind, patternProblem, presetForPattern, summarizeAnswerRules } from '@app/utils/answer-rules';
import { PatternHazard } from '@app/utils/pattern-safety';
import { NumberSetting, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';

type Patch = Partial<IFormFieldValidation>;

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
                        <>
                            <p className="text-[11px] leading-relaxed text-black-600">This question has a custom pattern from an import; it is still checked.</p>
                            <PatternHazardNotice pattern={rules.regex} stored />
                        </>
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

    // What the box holds can be a hazard (utils/pattern-safety.ts): it is not
    // handed to the form, so nothing the server would refuse is ever saved.
    const hazard = patternHazardOf(pattern);
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
                    value={preset?.id ?? (isCustom || hazard ? 'custom' : '')}
                    onChange={(event) => {
                        const value = event.target.value;
                        if (value === 'custom') {
                            setAdvancedOpen(true);
                            if (pattern) onChange({ regex: pattern });
                            return;
                        }
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
                        aria-describedby={hazard ? `${patternId}-hazard ${patternId}-hint` : `${patternId}-hint`}
                        aria-invalid={hazard ? true : undefined}
                        onChange={(event) => {
                            const next = event.target.value;
                            setPattern(next);
                            // an unsafe pattern is shown with its error but not saved
                            onChange({ regex: next && !patternHazardOf(next) ? next : undefined });
                        }}
                        className={`h-8 w-full rounded border bg-white px-2 font-mono text-xs focus:border-brand-500 ${hazard ? 'border-red-600' : 'border-control'}`}
                    />
                    <PatternHazardNotice pattern={pattern} stored={!!hazard && pattern === rules.regex} id={`${patternId}-hazard`} />
                    <p id={`${patternId}-hint`} className="text-[11px] leading-relaxed text-black-600">
                        Answers must match it (use ^ and $ to match the whole answer). Respondents see a general “not in the expected format” message, so say in the description what you expect.
                    </p>
                </div>
            </details>
        </>
    );
}

/** The hazard in a pattern that compiles (one that does not is reported by answerRuleConflicts), or null. */
function patternHazardOf(pattern: string | undefined): PatternHazard | null {
    const problem = patternProblem(pattern);
    return problem && problem !== 'invalid' && !(problem === 'too_complex' && (pattern?.length ?? 0) > PATTERN_MAX_LENGTH) ? problem : null;
}

/**
 * Why a pattern is refused: it can take a browser very long to check
 * (utils/pattern-safety.ts; the server refuses the same patterns when a form
 * is saved). `stored`: the form already holds it, so it is kept but skipped
 * by respondents' browsers.
 */
function PatternHazardNotice({ pattern, stored, id }: { pattern: string | undefined; stored?: boolean; id?: string }) {
    const { t } = useTranslation('builder');
    const hazard = patternHazardOf(pattern);
    if (!hazard) return null;
    return (
        <p id={id} role="alert" className="text-[11px] leading-relaxed text-red-700">
            {stored ? t('PATTERN_HAZARD.STORED_NOTE') : t('PATTERN_HAZARD.NOT_SAVED')} {t(`PATTERN_HAZARD.${hazard.toUpperCase()}`)}
        </p>
    );
}
