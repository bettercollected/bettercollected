'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';

import { AlertTriangle, ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { v4 as uuidv4 } from 'uuid';

import { FIELD_RULES_MAX, FORM_FIELD_RULES_MAX, FieldRule, FieldRuleCondition } from '@app/lib/field-rules';
import { FieldRuleProblem, canCarryRules, canLockOrSet, fieldRuleProblems, totalRules } from '@app/lib/form-ops/field-rule-checks';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { LogicCondition } from '@app/models/types/form-builder-shared';
import { CalculationVariable, calculationVariables } from '@app/utils/calculated-fields';
import { getGroupChildren, isRepeatingGroup } from '@app/utils/repeating-groups';
import { COMPARISON_LABELS, ConditionRow, SourceField, buildSourceFields, fieldText, isConditionComplete, isConditionSource, newConditionFor, selectClass } from '@app/views/molecules/form-builder/condition-editor-shared';
import FormulaInput from '@app/views/molecules/form-builder/formula-input';
import { SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';

const FORMULA_HELP = 'FIELD_RULES.FORMULA_HELP';
const inputClass = 'text-black-800 focus:border-brand-500 w-full min-w-0 rounded-md border border-control bg-white px-2 py-1.5 text-xs outline-hidden';
const buttonClass =
    'text-black-600 hover:text-black-800 hover:bg-black-100 focus-visible:ring-brand-500 inline-flex h-7 w-7 items-center justify-center rounded focus-visible:ring-2 focus-visible:outline-hidden disabled:opacity-40 disabled:hover:bg-transparent';

/** A question's rules as a section of the inspector: what the creator can change here, and nothing else. */
export interface FieldRulesSettingsProps {
    /** The question the rules are on. */
    field: StandardFormFieldDto;
    /** The form's pages (sources, formulas and the checks read them). */
    slides: StandardFormFieldDto[];
    hiddenNames: string[];
    /**
     * Put these rules on the question (undefined: none). True when the form took them; false when it
     * did not, and the editor keeps them as a draft with the reason shown. `coalesceKey` merges
     * typing into one undo step.
     */
    onChange: (rules: FieldRule[] | undefined, coalesceKey?: string) => boolean;
    /** Rules may be changed (the server accepts them); false: the rules are listed, not editable. */
    editable?: boolean;
    /** Add a first rule when the editor opens (it was opened by "Add a rule"). */
    addFirst?: boolean;
}

const newRuleId = () => `r_${uuidv4().replace(/-/g, '').slice(0, 10)}`;
const rulesOf = (field: StandardFormFieldDto): FieldRule[] => (Array.isArray(field.properties?.rules) ? (field.properties!.rules as FieldRule[]) : []);

/** The repeating group a question sits in, if any. */
function groupOf(slides: StandardFormFieldDto[], fieldId: string): StandardFormFieldDto | undefined {
    for (const slide of slides) for (const field of slide.properties?.fields ?? []) if (isRepeatingGroup(field) && (field.properties?.fields ?? []).some((child) => child.id === fieldId)) return field;
    return undefined;
}

/** The questions a rule may read: any other answerable question (a group's own questions only inside it), and groups as a whole. */
export function ruleSources(slides: StandardFormFieldDto[], field: StandardFormFieldDto): SourceField[] {
    const group = groupOf(slides, field.id);
    const sources = buildSourceFields(slides, (_slide, _index, candidate) => candidate.id !== field.id && isConditionSource(candidate) && !(group && candidate.id === group.id));
    if (group) {
        getGroupChildren(group).forEach((child) => {
            if (child.id !== field.id && !child.internal && isConditionSource(child)) sources.push({ field: child, label: fieldText(child) });
        });
    }
    return sources;
}

/** What a formula may read: the form's variables, and inside a repeating group the questions of the same item. */
function ruleVariables(slides: StandardFormFieldDto[], hiddenNames: string[], field: StandardFormFieldDto): CalculationVariable[] {
    const variables = calculationVariables(slides, hiddenNames).filter((variable) => variable.key !== field.id);
    const group = groupOf(slides, field.id);
    if (group) {
        getGroupChildren(group).forEach((child) => {
            if (child.id !== field.id && !child.internal && child.type !== FieldTypes.TEXT) variables.push({ key: child.id, label: fieldText(child), kind: 'field' });
        });
    }
    return variables;
}

/** `slides` with the rules of one question replaced (a copy along the path), for checking a draft before it is saved. */
function withRules(slides: StandardFormFieldDto[], fieldId: string, rules: FieldRule[]): StandardFormFieldDto[] {
    const swap = (list: StandardFormFieldDto[]): StandardFormFieldDto[] => {
        let changed = false;
        const next = list.map((item) => {
            if (item.id === fieldId) {
                changed = true;
                return { ...item, properties: { ...item.properties, rules } as StandardFormFieldDto['properties'] };
            }
            const children = item.properties?.fields;
            if (children?.length) {
                const inner = swap(children);
                if (inner !== children) {
                    changed = true;
                    return { ...item, properties: { ...item.properties, fields: inner } as StandardFormFieldDto['properties'] };
                }
            }
            return item;
        });
        return changed ? next : list;
    };
    return swap(slides);
}

/** The sources a condition can pick from; a question the form no longer has is listed (as such) so the row does not show another one in its place. */
function sourcesWith(condition: LogicCondition, sources: SourceField[], missing: string): SourceField[] {
    if (!condition.fieldId || sources.some((source) => source.field.id === condition.fieldId)) return sources;
    return [{ field: { id: condition.fieldId, index: 0, type: condition.fieldType as FieldTypes } as StandardFormFieldDto, label: missing }, ...sources];
}

type TriggerKind = 'conditions' | 'expression';
const triggerKind = (rule: FieldRule): TriggerKind => (rule.when?.expression !== undefined && rule.when?.expression !== null ? 'expression' : 'conditions');

/** Why a rule cannot be saved yet (what is left to fill in), or null. */
export function unfinishedReason(rule: FieldRule, field: StandardFormFieldDto): string | null {
    if (triggerKind(rule) === 'conditions') {
        const conditions = rule.when?.conditions ?? [];
        if (!conditions.length || conditions.some((condition) => !isConditionComplete(condition as unknown as LogicCondition))) return 'TRIGGER';
    }
    const then = rule.then ?? {};
    if (!['required', 'readOnly', 'title', 'description', 'setValue'].some((key) => (then as Record<string, unknown>)[key] !== undefined)) return 'EFFECT';
    if (typeof then.title === 'string' && !then.title.trim()) return 'TITLE';
    if (then.setValue) {
        const { const: value, expression } = then.setValue;
        if (expression === undefined && (value === undefined || value === null || value === '')) return 'VALUE';
    }
    void field;
    return null;
}

export default function FieldRulesSettings({ field, slides, hiddenNames, onChange, editable = true, addFirst = false }: FieldRulesSettingsProps) {
    const { t } = useTranslation('builder');
    const id = useId();
    const stored = rulesOf(field);
    const storedJson = JSON.stringify(stored);
    // What the creator is editing: the form's rules, or a draft that is not valid yet.
    const [draft, setDraft] = useState<FieldRule[] | null>(null);
    const [seen, setSeen] = useState(storedJson);
    if (seen !== storedJson) {
        // Changed elsewhere (undo, the AI, another tab): show what the form has, unless the draft says the same.
        setSeen(storedJson);
        if (draft && JSON.stringify(draft) !== storedJson) setDraft(null);
    }
    const rules = draft ?? stored;
    const [announcement, setAnnouncement] = useState('');
    const addRef = useRef<HTMLButtonElement>(null);
    const didAddFirst = useRef(false);

    const sources = useMemo(() => ruleSources(slides, field), [slides, field]);
    const variables = useMemo(() => ruleVariables(slides, hiddenNames, field), [slides, hiddenNames, field]);
    const inGroup = !!groupOf(slides, field.id);
    const lockable = canLockOrSet(field, inGroup);
    const formTotal = useMemo(() => totalRules({ fields: slides }), [slides]);

    // The shared checks (the server's own, in the same words) over the form as it would be with these rules.
    const problems = useMemo<FieldRuleProblem[]>(() => (rules.length ? fieldRuleProblems({ fields: withRules(slides, field.id, rules), hiddenFields: hiddenNames }, { only: [field.id], limit: null }) : []), [slides, field.id, rules, hiddenNames]);
    const known = useMemo(() => new Set(fieldRuleProblems({ fields: slides, hiddenFields: hiddenNames }, { only: [field.id], limit: null }).map((problem) => problem.message)), [slides, hiddenNames, field.id]);
    const ownProblems = problems.filter((problem) => problem.fieldId === field.id);
    const formProblems = problems.filter((problem) => problem.fieldId !== field.id);

    const commit = (next: FieldRule[], coalesceKey?: string) => {
        const check = fieldRuleProblems({ fields: withRules(slides, field.id, next), hiddenFields: hiddenNames }, { only: [field.id], limit: null });
        const blocked = check.some((problem) => !known.has(problem.message)) || next.some((rule) => unfinishedReason(rule, field) !== null);
        if (!blocked && onChange(next.length ? next : undefined, coalesceKey)) {
            setDraft(null);
            return;
        }
        setDraft(next);
    };
    const edit = (index: number, change: (rule: FieldRule) => FieldRule, coalesceKey?: string) =>
        commit(
            rules.map((rule, i) => (i === index ? change(rule) : rule)),
            coalesceKey ? `rules:${field.id}:${rules[index]?.id}:${coalesceKey}` : undefined
        );

    const addRule = () => {
        const first = sources[0]?.field;
        const when: FieldRule['when'] = first && !isRepeatingGroup(first) ? { conditions: [{ fieldId: first.id, fieldType: first.type, comparison: 'IS_NOT_EMPTY' }] } : { expression: true };
        commit([...rules, { id: newRuleId(), when, then: { required: true } }]);
        setAnnouncement(t('FIELD_RULES.ANNOUNCE_ADDED', { n: rules.length + 1 }));
    };
    // Opened by "Add a rule": start with one (once).
    useEffect(() => {
        if (addFirst && editable && !didAddFirst.current) {
            didAddFirst.current = true;
            if (!rules.length) addRule();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [addFirst, editable]);
    if (!canCarryRules(field)) return null;

    const move = (index: number, by: -1 | 1) => {
        const next = [...rules];
        [next[index], next[index + by]] = [next[index + by], next[index]];
        commit(next);
        setAnnouncement(t('FIELD_RULES.ANNOUNCE_MOVED', { from: index + 1, to: index + 1 + by }));
    };
    const remove = (index: number) => {
        commit(rules.filter((_, i) => i !== index));
        setAnnouncement(t('FIELD_RULES.ANNOUNCE_DELETED', { n: index + 1 }));
        window.setTimeout(() => addRef.current?.focus(), 0);
    };

    const atFieldCap = rules.length >= FIELD_RULES_MAX;
    const atFormCap = formTotal >= FORM_FIELD_RULES_MAX && !draft;

    if (!editable) {
        return (
            <div className="flex w-full flex-col gap-2" data-testid="field-rules-readonly">
                <p className="text-[11px] leading-relaxed text-black-600">{t('FIELD_RULES.DISABLED_NOTE')}</p>
                <ol className="flex flex-col gap-1.5">
                    {rules.map((rule, index) => (
                        <li key={rule.id} className="rounded-md border border-black-300 bg-black-100 px-2 py-1.5 text-xs text-black-800">
                            {t('FIELD_RULES.RULE_N', { n: index + 1 })}: {ruleSummary(rule, slides, field, t)}
                        </li>
                    ))}
                </ol>
            </div>
        );
    }

    return (
        <div className="flex w-full flex-col gap-3">
            <p className="text-[11px] leading-relaxed text-black-600">{t('FIELD_RULES.INTRO')}</p>
            <div role="status" aria-live="polite" className="sr-only">
                {announcement}
            </div>

            {rules.length === 0 && <p className="rounded-md border border-dashed border-black-300 px-3 py-3 text-xs leading-relaxed text-black-600">{t('FIELD_RULES.EMPTY')}</p>}

            {rules.map((rule, index) => (
                <RuleCard
                    key={rule.id}
                    rule={rule}
                    index={index}
                    count={rules.length}
                    field={field}
                    slides={slides}
                    sources={sources}
                    variables={variables}
                    lockable={lockable}
                    inGroup={inGroup}
                    problems={ownProblems.filter((problem) => problem.rule === index)}
                    unfinished={unfinishedReason(rule, field)}
                    summary={ruleSummary(rule, slides, field, t)}
                    onEdit={(change, key) => edit(index, change, key)}
                    onMove={(by) => move(index, by)}
                    onRemove={() => remove(index)}
                />
            ))}

            {ownProblems.filter((problem) => problem.rule === undefined).concat(formProblems).length > 0 && (
                <ul className="flex flex-col gap-1" aria-label={t('FIELD_RULES.PROBLEMS')}>
                    {ownProblems
                        .filter((problem) => problem.rule === undefined)
                        .concat(formProblems)
                        .map((problem, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-800">
                                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                                <span>{problem.message}</span>
                            </li>
                        ))}
                </ul>
            )}

            <button
                ref={addRef}
                type="button"
                disabled={atFieldCap || atFormCap}
                aria-describedby={atFieldCap || atFormCap ? `${id}-cap` : undefined}
                onClick={addRule}
                className="inline-flex w-fit items-center gap-1 rounded text-xs font-medium text-brand-500 hover:text-brand-600 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden disabled:opacity-50"
            >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                {t('FIELD_RULES.ADD')}
            </button>
            {(atFieldCap || atFormCap) && (
                <p id={`${id}-cap`} className="text-[11px] text-black-600">
                    {atFieldCap ? t('FIELD_RULES.CAP_FIELD', { max: FIELD_RULES_MAX }) : t('FIELD_RULES.CAP_FORM', { max: FORM_FIELD_RULES_MAX })}
                </p>
            )}
            {rules.length > 1 && <p className="text-[11px] leading-relaxed text-black-600">{t('FIELD_RULES.ORDER_HINT')}</p>}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Summaries
// ---------------------------------------------------------------------------

type T = (key: string, options?: Record<string, unknown>) => string;

const valueText = (value: unknown): string => (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : '');

/** One line for a rule: "When Country is equal to NL: require, set a value". */
export function ruleSummary(rule: FieldRule, slides: StandardFormFieldDto[], field: StandardFormFieldDto, t: T): string {
    const label = (id?: string) => {
        for (const slide of slides)
            for (const item of slide.properties?.fields ?? []) {
                if (item.id === id) return fieldText(item);
                for (const child of item.properties?.fields ?? []) if (child.id === id) return fieldText(child);
            }
        return id || '?';
    };
    const when =
        triggerKind(rule) === 'expression'
            ? t('FIELD_RULES.SUMMARY_FORMULA')
            : (rule.when?.conditions ?? [])
                  .map((c: FieldRuleCondition) => `${label(c.fieldId)} ${COMPARISON_LABELS[String(c.comparison)] ?? ''}${c.value !== undefined && c.value !== '' ? ` ${valueText(c.value)}` : ''}`.trim())
                  .join(rule.when?.operator === 'OR' ? ` ${t('FIELD_RULES.OR')} ` : ` ${t('FIELD_RULES.AND')} `);
    const then = rule.then ?? {};
    const effects: string[] = [];
    if (then.required !== undefined) effects.push(then.required ? t('FIELD_RULES.SUMMARY_REQUIRE') : t('FIELD_RULES.SUMMARY_OPTIONAL'));
    if (then.setValue) effects.push(t('FIELD_RULES.SUMMARY_SET'));
    else if (then.readOnly) effects.push(t('FIELD_RULES.SUMMARY_LOCK'));
    if (then.title !== undefined) effects.push(t('FIELD_RULES.SUMMARY_TITLE'));
    if (then.description !== undefined) effects.push(t('FIELD_RULES.SUMMARY_DESCRIPTION'));
    void field;
    return `${t('FIELD_RULES.WHEN')} ${when}: ${effects.join(', ')}`;
}

// ---------------------------------------------------------------------------
// One rule
// ---------------------------------------------------------------------------

interface RuleCardProps {
    rule: FieldRule;
    index: number;
    count: number;
    field: StandardFormFieldDto;
    slides: StandardFormFieldDto[];
    sources: SourceField[];
    variables: CalculationVariable[];
    lockable: boolean;
    inGroup: boolean;
    problems: FieldRuleProblem[];
    unfinished: string | null;
    summary: string;
    onEdit: (change: (rule: FieldRule) => FieldRule, coalesceKey?: string) => void;
    onMove: (by: -1 | 1) => void;
    onRemove: () => void;
}

function RuleCard({ rule, index, count, field, sources, variables, lockable, inGroup, problems, unfinished, summary, onEdit, onMove, onRemove }: RuleCardProps) {
    const { t } = useTranslation('builder');
    const id = useId();
    const kind = triggerKind(rule);
    const conditions = (rule.when?.conditions ?? []) as unknown as LogicCondition[];
    const then = rule.then ?? {};
    const n = index + 1;

    const setWhen = (when: FieldRule['when'], key?: string) => onEdit((r) => ({ ...r, when }), key);
    const setThen = (patch: Partial<FieldRule['then']>, key?: string) =>
        onEdit((r) => {
            const next = { ...r.then, ...patch } as Record<string, unknown>;
            Object.keys(next).forEach((k) => next[k] === undefined && delete next[k]);
            return { ...r, then: next as FieldRule['then'] };
        }, key);
    const patchCondition = (at: number, patch: Partial<LogicCondition>) => setWhen({ ...rule.when, conditions: conditions.map((c, i) => (i === at ? { ...c, ...patch } : c)) as unknown as FieldRuleCondition[] });

    const describedBy = [problems.length ? `${id}-problems` : '', unfinished ? `${id}-unfinished` : ''].filter(Boolean).join(' ') || undefined;
    const readOnlyNoValue = !!then.readOnly && !then.setValue;
    const valueField = field;

    return (
        <fieldset aria-describedby={describedBy} className="flex min-w-0 flex-col gap-3 rounded-lg border border-black-300 bg-white p-3" data-testid={`field-rule-${n}`}>
            <legend className="sr-only">{t('FIELD_RULES.RULE_N', { n })}</legend>
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="text-xs font-semibold text-black-800">{t('FIELD_RULES.RULE_N', { n })}</div>
                    <div className="text-[11px] leading-relaxed text-black-600" data-testid="rule-summary">
                        {summary}
                    </div>
                </div>
                <div className="flex shrink-0 items-center">
                    <button type="button" className={buttonClass} disabled={index === 0} aria-label={t('FIELD_RULES.MOVE_UP', { n })} onClick={() => onMove(-1)}>
                        <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                    <button type="button" className={buttonClass} disabled={index === count - 1} aria-label={t('FIELD_RULES.MOVE_DOWN', { n })} onClick={() => onMove(1)}>
                        <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                    <button type="button" className={buttonClass} aria-label={t('FIELD_RULES.DELETE', { n })} onClick={onRemove}>
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                </div>
            </div>

            {/* When */}
            <div className="flex flex-col gap-2">
                <label htmlFor={`${id}-kind`} className="text-xs font-medium text-black-700">
                    {t('FIELD_RULES.WHEN_LABEL')}
                </label>
                <select
                    id={`${id}-kind`}
                    className={selectClass}
                    value={kind}
                    onChange={(e) => {
                        if (e.target.value === 'expression') setWhen({ expression: true });
                        else setWhen({ operator: 'AND', conditions: [newConditionFor(sources) as unknown as FieldRuleCondition] });
                    }}
                >
                    <option value="conditions">{t('FIELD_RULES.WHEN_ANSWERS')}</option>
                    <option value="expression">{t('FIELD_RULES.WHEN_FORMULA')}</option>
                </select>
                {kind === 'conditions' ? (
                    sources.length === 0 ? (
                        <p className="text-[11px] text-black-600">{t('FIELD_RULES.NO_SOURCES')}</p>
                    ) : (
                        <div className="flex flex-col gap-2">
                            {conditions.length > 1 && (
                                <div className="flex items-center gap-1 text-xs text-black-600">
                                    <span className="shrink-0">{t('FIELD_RULES.MATCH')}</span>
                                    <select aria-label={t('FIELD_RULES.MATCH_LABEL')} className={selectClass} value={rule.when?.operator ?? 'AND'} onChange={(e) => setWhen({ ...rule.when, operator: e.target.value as 'AND' | 'OR' })}>
                                        <option value="AND">{t('FIELD_RULES.MATCH_ALL')}</option>
                                        <option value="OR">{t('FIELD_RULES.MATCH_ANY')}</option>
                                    </select>
                                    <span className="shrink-0">{t('FIELD_RULES.MATCH_OF')}</span>
                                </div>
                            )}
                            {conditions.map((condition, at) => (
                                <ConditionRow
                                    key={at}
                                    condition={condition}
                                    sources={sourcesWith(condition, sources, t('FIELD_RULES.MISSING_SOURCE'))}
                                    onChange={(patch) => patchCondition(at, patch)}
                                    onRemove={conditions.length > 1 ? () => setWhen({ ...rule.when, conditions: conditions.filter((_, i) => i !== at) as unknown as FieldRuleCondition[] }) : undefined}
                                />
                            ))}
                            <button
                                type="button"
                                className="w-fit rounded text-xs font-medium text-brand-500 hover:text-brand-600 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                                onClick={() => setWhen({ ...rule.when, conditions: [...conditions, newConditionFor(sources) as unknown as FieldRuleCondition] as FieldRuleCondition[] })}
                            >
                                + {t('FIELD_RULES.ADD_CONDITION')}
                            </button>
                        </div>
                    )
                ) : (
                    <FormulaInput
                        label={t('FIELD_RULES.FORMULA_LABEL')}
                        resetKey={rule.id}
                        expression={rule.when?.expression}
                        variables={variables}
                        onExpression={(expression) => setWhen({ expression }, 'when')}
                        rows={2}
                        placeholder={t('FIELD_RULES.FORMULA_PLACEHOLDER')}
                        help={t(FORMULA_HELP)}
                        invalid={problems.some((problem) => problem.path.startsWith(`/${index}/when/expression`))}
                    />
                )}
            </div>

            {/* Then */}
            <div className="flex flex-col gap-3">
                <div className="text-xs font-medium text-black-700">{t('FIELD_RULES.THEN_LABEL')}</div>

                <div className="flex flex-col gap-1.5">
                    <SettingSwitch label={t('FIELD_RULES.EFFECT_REQUIRED')} checked={then.required !== undefined} onCheckedChange={(on) => setThen({ required: on ? true : undefined })} />
                    {then.required !== undefined && (
                        <select aria-label={t('FIELD_RULES.REQUIRED_CHOICE')} className={selectClass} value={then.required ? 'yes' : 'no'} onChange={(e) => setThen({ required: e.target.value === 'yes' })}>
                            <option value="yes">{t('FIELD_RULES.REQUIRED_YES')}</option>
                            <option value="no">{t('FIELD_RULES.REQUIRED_NO')}</option>
                        </select>
                    )}
                </div>

                {lockable ? (
                    <>
                        <SettingSwitch
                            label={t('FIELD_RULES.EFFECT_LOCK')}
                            checked={!!then.readOnly || !!then.setValue}
                            disabled={!!then.setValue}
                            onCheckedChange={(on) => setThen({ readOnly: on ? true : undefined })}
                            hint={then.setValue ? t('FIELD_RULES.LOCK_BY_VALUE') : t('FIELD_RULES.LOCK_HINT')}
                        />
                        <div className="flex flex-col gap-1.5">
                            <SettingSwitch
                                label={t('FIELD_RULES.EFFECT_VALUE')}
                                checked={!!then.setValue}
                                onCheckedChange={(on) => setThen(on ? { setValue: field.type === FieldTypes.YES_NO ? { const: true } : isChoice(field) ? { const: '' } : { expression: 1 }, readOnly: undefined } : { setValue: undefined })}
                            />
                            {then.setValue && (
                                <ValueEditor field={valueField} value={then.setValue} variables={variables} ruleId={rule.id} onChange={(setValue, key) => setThen({ setValue }, key)} invalid={problems.some((p) => p.path.includes('/then/setValue'))} />
                            )}
                        </div>
                    </>
                ) : (
                    <p className="text-[11px] leading-relaxed text-black-600">{inGroup ? t('FIELD_RULES.LOCK_UNAVAILABLE_GROUP') : t('FIELD_RULES.LOCK_UNAVAILABLE')}</p>
                )}

                <div className="flex flex-col gap-1.5">
                    <SettingSwitch label={t('FIELD_RULES.EFFECT_TITLE')} checked={then.title !== undefined} onCheckedChange={(on) => setThen({ title: on ? '' : undefined })} />
                    {then.title !== undefined && (
                        <>
                            <input aria-label={t('FIELD_RULES.TITLE_INPUT')} className={inputClass} type="text" maxLength={300} value={then.title} onChange={(e) => setThen({ title: e.target.value }, 'title')} />
                            <p className="text-[11px] leading-relaxed text-black-600">{t('FIELD_RULES.HINT_CONSENT')}</p>
                        </>
                    )}
                </div>
                <div className="flex flex-col gap-1.5">
                    <SettingSwitch label={t('FIELD_RULES.EFFECT_DESCRIPTION')} checked={then.description !== undefined} onCheckedChange={(on) => setThen({ description: on ? '' : undefined })} />
                    {then.description !== undefined && (
                        <textarea aria-label={t('FIELD_RULES.DESCRIPTION_INPUT')} className={inputClass} rows={2} maxLength={1000} value={then.description} onChange={(e) => setThen({ description: e.target.value }, 'description')} />
                    )}
                </div>
            </div>

            {readOnlyNoValue && (
                <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-800" data-testid="warn-read-only-no-value">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                    <span>{t('FIELD_RULES.WARN_READ_ONLY_NO_VALUE')}</span>
                </p>
            )}
            {problems.length > 0 && (
                <ul id={`${id}-problems`} className="flex flex-col gap-1">
                    {problems.map((problem, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-800">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                            <span>{problem.message}</span>
                        </li>
                    ))}
                </ul>
            )}
            {unfinished && (
                <p id={`${id}-unfinished`} className="text-[11px] leading-relaxed text-black-600" data-testid="rule-unfinished">
                    {t(`FIELD_RULES.UNFINISHED_${unfinished}`)}
                </p>
            )}
        </fieldset>
    );
}

const isChoice = (field: StandardFormFieldDto) => field.type === FieldTypes.MULTIPLE_CHOICE || field.type === FieldTypes.DROP_DOWN;

// ---------------------------------------------------------------------------
// The value a rule sets
// ---------------------------------------------------------------------------

function ValueEditor({
    field,
    value,
    variables,
    ruleId,
    onChange,
    invalid
}: {
    field: StandardFormFieldDto;
    value: NonNullable<FieldRule['then']['setValue']>;
    variables: CalculationVariable[];
    ruleId: string;
    onChange: (value: NonNullable<FieldRule['then']['setValue']>, coalesceKey?: string) => void;
    invalid: boolean;
}) {
    const { t } = useTranslation('builder');
    const id = useId();
    const asFormula = value.expression !== undefined && value.expression !== null;
    const choice = isChoice(field);
    const constant = value.const;

    const constInput = () => {
        if (choice) {
            return (
                <select aria-label={t('FIELD_RULES.VALUE_OPTION')} className={selectClass} value={String(constant ?? '')} onChange={(e) => onChange({ const: e.target.value })}>
                    <option value="">{t('FIELD_RULES.VALUE_CHOOSE')}</option>
                    {(field.properties?.choices ?? []).map((option) => (
                        <option key={option.id} value={option.id}>
                            {option.value || option.label || '—'}
                        </option>
                    ))}
                </select>
            );
        }
        if (field.type === FieldTypes.YES_NO) {
            return (
                <select aria-label={t('FIELD_RULES.VALUE_YES_NO')} className={selectClass} value={constant === false ? 'no' : constant === true ? 'yes' : ''} onChange={(e) => onChange({ const: e.target.value === 'yes' })}>
                    <option value="yes">{t('FIELD_RULES.VALUE_YES')}</option>
                    <option value="no">{t('FIELD_RULES.VALUE_NO')}</option>
                </select>
            );
        }
        const type = field.type === FieldTypes.NUMBER ? 'number' : field.type === FieldTypes.DATE ? 'date' : 'text';
        return (
            <input
                aria-label={t('FIELD_RULES.VALUE_INPUT')}
                className={`${inputClass} ${invalid ? 'border-amber-400' : ''}`}
                type={type}
                value={constant === undefined || constant === null ? '' : String(constant)}
                onChange={(e) => {
                    const raw = e.target.value;
                    onChange({ const: type === 'number' ? (raw === '' || Number.isNaN(Number(raw)) ? '' : Number(raw)) : raw } as NonNullable<FieldRule['then']['setValue']>, 'value');
                }}
            />
        );
    };

    return (
        <div className="flex flex-col gap-1.5">
            {!choice && (
                <div className="flex items-center gap-3 text-xs text-black-700" role="radiogroup" aria-label={t('FIELD_RULES.VALUE_KIND')}>
                    <label className="inline-flex items-center gap-1">
                        <input type="radio" name={`${id}-kind`} checked={!asFormula} onChange={() => onChange(field.type === FieldTypes.YES_NO ? { const: true } : { const: field.type === FieldTypes.NUMBER ? 0 : '' })} />
                        {t('FIELD_RULES.VALUE_CONST')}
                    </label>
                    <label className="inline-flex items-center gap-1">
                        <input type="radio" name={`${id}-kind`} checked={asFormula} onChange={() => onChange({ expression: 1 })} />
                        {t('FIELD_RULES.VALUE_FORMULA')}
                    </label>
                </div>
            )}
            {asFormula ? (
                <FormulaInput
                    label={t('FIELD_RULES.VALUE_FORMULA_LABEL')}
                    resetKey={`${ruleId}:value`}
                    expression={value.expression}
                    variables={variables}
                    onExpression={(expression) => onChange({ expression }, 'value')}
                    rows={2}
                    placeholder={t('FIELD_RULES.FORMULA_PLACEHOLDER_VALUE')}
                    help={t(FORMULA_HELP)}
                    invalid={invalid}
                />
            ) : (
                constInput()
            )}
        </div>
    );
}
