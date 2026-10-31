'use client';

import React, { useId, useMemo } from 'react';

import { useTranslation } from 'react-i18next';

import { FieldTypes } from '@app/models/dtos/form';
import { LogicalOperator } from '@app/models/types/form-builder-shared';
import { Switch } from '@app/shadcn/components/ui/switch';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import type { ActionCondition } from '@app/store/workspaces/webhooks-api';
import { ConditionRow, buildSourceFields, isConditionComplete, isConditionSource, newConditionFor, selectClass } from '@app/views/molecules/form-builder/condition-editor-shared';

// What the server accepts as a condition source (services/action_conditions.py):
// answerable questions of a page, calculations and repeating groups, never files,
// matrices or the questions inside a group.
const SERVER_UNSUPPORTED = new Set<string>([FieldTypes.MATRIX, FieldTypes.TABULAR_INPUT, FieldTypes.FILE_UPLOAD]);

/** Whether every condition is complete (a field, a comparison and, where needed, a value). */
export const conditionIncomplete = (value: ActionCondition | null | undefined) => !!value && value.conditions.some((c) => !isConditionComplete(c));

/**
 * "Only run when": the condition under which a webhook or an email action runs,
 * built from the form's own logic conditions. The server evaluates it on the
 * submitted answers; this only writes it. Off (null): every submission.
 */
export default function ActionConditionEditor({ value, onChange, error, idPrefix = 'action' }: { value: ActionCondition | null; onChange: (next: ActionCondition | null) => void; error?: string | null; idPrefix?: string }) {
    const { t } = useTranslation('builder');
    const form = useAppSelector(selectForm);
    const titleId = useId();
    const sources = useMemo(() => buildSourceFields((form?.fields as any) ?? [], (_slide, _index, field) => isConditionSource(field) && !SERVER_UNSUPPORTED.has(field.type as string)), [form?.fields]);
    const enabled = !!value;
    const incomplete = conditionIncomplete(value);

    const toggle = (on: boolean) => onChange(on ? { operator: LogicalOperator.AND, conditions: [newConditionFor(sources)] } : null);

    return (
        <fieldset className="flex flex-col gap-3" data-testid={`${idPrefix}-condition`} aria-labelledby={titleId}>
            <div className="flex items-start justify-between gap-4">
                <div className="flex flex-col gap-1">
                    <legend id={titleId} className="text-sm font-medium text-black-900">
                        {t('ACTION_CONDITION.TITLE')}
                    </legend>
                    <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('ACTION_CONDITION.HINT')}</p>
                </div>
                <Switch id={`${idPrefix}-condition-on`} checked={enabled} disabled={sources.length === 0 && !enabled} aria-labelledby={titleId} onCheckedChange={toggle} />
            </div>
            {sources.length === 0 && !enabled && <p className="text-xs text-black-600">{t('ACTION_CONDITION.NO_QUESTIONS')}</p>}

            {value && (
                <div className="flex flex-col gap-3">
                    {value.conditions.length > 1 && (
                        <div className="flex items-center gap-2 text-xs text-black-700">
                            <label htmlFor={`${idPrefix}-condition-operator`} className="shrink-0">
                                {t('ACTION_CONDITION.MATCH')}
                            </label>
                            <select id={`${idPrefix}-condition-operator`} className={selectClass + ' max-w-40'} value={value.operator} onChange={(e) => onChange({ ...value, operator: e.target.value as LogicalOperator })}>
                                <option value={LogicalOperator.AND}>{t('ACTION_CONDITION.ALL')}</option>
                                <option value={LogicalOperator.OR}>{t('ACTION_CONDITION.ANY')}</option>
                            </select>
                            <span>{t('ACTION_CONDITION.OF_THESE')}</span>
                        </div>
                    )}
                    {value.conditions.map((condition, index) => (
                        <ConditionRow
                            key={index}
                            condition={condition}
                            sources={sources}
                            onChange={(patch) => onChange({ ...value, conditions: value.conditions.map((c, i) => (i === index ? { ...c, ...patch } : c)) })}
                            onRemove={value.conditions.length > 1 ? () => onChange({ ...value, conditions: value.conditions.filter((_, i) => i !== index) }) : undefined}
                        />
                    ))}
                    {value.conditions.length < 10 && (
                        <button type="button" className="w-fit text-xs font-medium text-brand-500 hover:text-brand-600" onClick={() => onChange({ ...value, conditions: [...value.conditions, newConditionFor(sources)] })}>
                            {t('ACTION_CONDITION.ADD')}
                        </button>
                    )}
                    <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('ACTION_CONDITION.NOT_MET')}</p>
                    {incomplete && (
                        <p role="alert" className="text-xs font-medium text-[#A83434]">
                            {t('ACTION_CONDITION.INCOMPLETE')}
                        </p>
                    )}
                </div>
            )}
            {error && (
                <p role="alert" className="text-xs font-medium text-[#A83434]">
                    {error}
                </p>
            )}
        </fieldset>
    );
}
