'use client';

import { useEffect, useState } from 'react';

import { X } from 'lucide-react';

import { useTranslation } from 'react-i18next';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { DateRule, DateRuleComparison } from '@app/models/types/form-builder-shared';
import { DATE_RULES_MAX, DATE_RULE_COMPARISON_LABELS, DateRuleSource, isIsoDate, todayIso } from '@app/utils/date-rules';

import { selectClass } from './condition-editor-shared';

const COMPARISONS = Object.keys(DATE_RULE_COMPARISON_LABELS) as DateRuleComparison[];

/** `<select>` value for a rule's target: `today`, `date` or `field:<id>`. */
const targetValue = (rule: DateRule) => (rule.target === 'field' ? `field:${rule.fieldId ?? ''}` : rule.target);

function targetFromValue(value: string, rule: DateRule): DateRule {
    if (value.startsWith('field:')) return { comparison: rule.comparison, target: 'field', fieldId: value.slice('field:'.length) };
    if (value === 'date') return { comparison: rule.comparison, target: 'date', date: isIsoDate(rule.date) ? rule.date : todayIso() };
    return { comparison: rule.comparison, target: 'today' };
}

/**
 * Settings of a date question: an optional short label shown with the picker
 * ("Start date") and up to DATE_RULES_MAX date rules — before / after / on or
 * before / on or after a fixed date, today, or an earlier date question
 * (`sources`: titles shown, ids stored). `onChange` receives the properties
 * to merge; an empty label or rule list is stored as `undefined`. A date range
 * has no label (its two pickers are named Start and End) and its rules apply
 * to each of its two days.
 */
export default function DateFieldSettings({
    field,
    sources,
    onChange,
    sourceHint
}: {
    field: StandardFormFieldDto;
    sources: DateRuleSource[];
    onChange: (patch: { label?: string; dateRules?: DateRule[] }) => void;
    sourceHint?: string;
}) {
    const { t } = useTranslation('builder');
    const rules = field.properties?.dateRules ?? [];
    const isRange = field.type === FieldTypes.DATE_RANGE;
    const [label, setLabel] = useState(field.properties?.label ?? '');

    useEffect(() => {
        setLabel(field.properties?.label ?? '');
    }, [field.id, field.properties?.label]);

    const saveRules = (next: DateRule[]) => onChange({ dateRules: next.length ? next : undefined });
    const patchRule = (index: number, next: DateRule) => saveRules(rules.map((rule, i) => (i === index ? next : rule)));
    const addRule = () => saveRules([...rules, sources.length ? { comparison: 'after', target: 'field', fieldId: sources[sources.length - 1].id } : { comparison: 'on_or_after', target: 'today' }]);

    return (
        <div className="flex flex-col gap-3" data-testid="date-field-settings">
            {!isRange && (
                <label className="flex flex-col gap-1 text-xs text-black-700">
                    {t('DATE_RULES.LABEL')}
                    <input
                        className={selectClass}
                        value={label}
                        placeholder={t('DATE_RULES.LABEL_PLACEHOLDER')}
                        maxLength={120}
                        onChange={(e) => setLabel(e.target.value)}
                        onBlur={() => {
                            const next = label.trim();
                            if (next !== (field.properties?.label ?? '')) onChange({ label: next || undefined });
                        }}
                    />
                    <span className="text-[11px] text-black-600">{t('DATE_RULES.LABEL_HINT')}</span>
                </label>
            )}

            <div className="flex flex-col gap-2">
                <div>
                    <div className="text-xs font-medium text-black-700">{t('DATE_RULES.TITLE')}</div>
                    <div className="text-[11px] text-black-600">
                        {isRange ? t('DATE_RULES.HINT_RANGE') : t('DATE_RULES.HINT_DATE')}
                        {t('DATE_RULES.HINT_APPLIES')}
                    </div>
                </div>
                {rules.map((rule, index) => {
                    const known = rule.target !== 'field' || sources.some((s) => s.id === rule.fieldId);
                    return (
                        <div key={index} className="flex flex-col gap-1.5 rounded-md border border-black-300 bg-white p-2" data-testid="date-rule">
                            <div className="flex items-center gap-1.5">
                                <span className="shrink-0 text-xs text-black-600">{t('DATE_RULES.MUST_BE')}</span>
                                <select aria-label={t('DATE_RULES.RULE_COMPARISON', { n: index + 1 })} className={selectClass} value={rule.comparison} onChange={(e) => patchRule(index, { ...rule, comparison: e.target.value as DateRuleComparison })}>
                                    {COMPARISONS.map((comparison) => (
                                        <option key={comparison} value={comparison}>
                                            {t(`DATE_RULES.CMP_${comparison}`, { defaultValue: DATE_RULE_COMPARISON_LABELS[comparison] })}
                                        </option>
                                    ))}
                                </select>
                                <button type="button" className="shrink-0 rounded p-1 text-black-600 hover:text-black-800" aria-label={t('DATE_RULES.REMOVE_RULE', { n: index + 1 })} onClick={() => saveRules(rules.filter((_, i) => i !== index))}>
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            </div>
                            <select aria-label={t('DATE_RULES.RULE_COMPARES', { n: index + 1 })} className={selectClass} value={targetValue(rule)} onChange={(e) => patchRule(index, targetFromValue(e.target.value, rule))}>
                                {sources.length > 0 && (
                                    <optgroup label={t('DATE_RULES.ANSWER_TO')}>
                                        {sources.map((source) => (
                                            <option key={source.id} value={`field:${source.id}`}>
                                                {source.label}
                                            </option>
                                        ))}
                                    </optgroup>
                                )}
                                {!known && <option value={targetValue(rule)}>{t('DATE_RULES.UNUSABLE')}</option>}
                                <option value="today">{t('DATE_RULES.TODAY')}</option>
                                <option value="date">{t('DATE_RULES.FIXED')}</option>
                            </select>
                            {rule.target === 'date' && (
                                <input type="date" aria-label={t('DATE_RULES.RULE_DATE', { n: index + 1 })} className={selectClass} value={rule.date ?? ''} onChange={(e) => isIsoDate(e.target.value) && patchRule(index, { ...rule, date: e.target.value })} />
                            )}
                            {!known && <span className="text-[11px] text-amber-700">{t('DATE_RULES.PICK_OTHER')}</span>}
                        </div>
                    );
                })}
                {rules.length < DATE_RULES_MAX && (
                    <button type="button" className="w-fit text-xs font-medium text-brand-500 hover:text-brand-600" onClick={addRule}>
                        {t('DATE_RULES.ADD')}
                    </button>
                )}
                {sources.length === 0 && <span className="text-[11px] text-black-600">{sourceHint ?? t('DATE_RULES.SOURCE_HINT')}</span>}
            </div>
        </div>
    );
}
