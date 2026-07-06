'use client';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicCondition } from '@app/models/types/form-builder-shared';
import { X } from 'lucide-react';

// Plain-text label from a field's Tiptap-JSON (or string) title, for the source picker.
export function fieldLabel(field: StandardFormFieldDto | undefined, fallback: string): string {
    const t: any = field?.title ?? field?.value;
    if (typeof t === 'string' && t.trim()) return t.trim();
    const walk = (node: any): string => {
        if (!node) return '';
        if (typeof node.text === 'string') return node.text;
        if (Array.isArray(node.content)) return node.content.map(walk).join('');
        return '';
    };
    return walk(t).trim() || fallback;
}

export const COMPARISON_LABELS: Record<string, string> = {
    [Comparison.IS_EQUAL]: 'is equal to',
    [Comparison.IS_NOT_EQUAL]: 'is not equal to',
    [Comparison.CONTAINS]: 'contains',
    [Comparison.DOES_NOT_CONTAIN]: 'does not contain',
    [Comparison.GREATER_THAN]: 'is greater than',
    [Comparison.GREATER_THAN_EQUAL]: 'is at least',
    [Comparison.LESS_THAN]: 'is less than',
    [Comparison.LESS_THAN_EQUAL]: 'is at most',
    [Comparison.STARTS_WITH]: 'starts with',
    [Comparison.ENDS_WITH]: 'ends with',
    [Comparison.IS_EMPTY]: 'is empty',
    [Comparison.IS_NOT_EMPTY]: 'is not empty'
};

const TEXT_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.CONTAINS, Comparison.DOES_NOT_CONTAIN, Comparison.STARTS_WITH, Comparison.ENDS_WITH, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const NUMBER_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.GREATER_THAN, Comparison.GREATER_THAN_EQUAL, Comparison.LESS_THAN, Comparison.LESS_THAN_EQUAL, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const CHOICE_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const MULTI_COMPARISONS = [Comparison.CONTAINS, Comparison.DOES_NOT_CONTAIN, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const DATE_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.GREATER_THAN, Comparison.LESS_THAN, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const BOOL_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL];

export function comparisonsForField(field?: StandardFormFieldDto): Comparison[] {
    switch (field?.type) {
        case FieldTypes.YES_NO:
            return BOOL_COMPARISONS;
        case FieldTypes.NUMBER:
        case FieldTypes.RATING:
        case FieldTypes.LINEAR_RATING:
            return NUMBER_COMPARISONS;
        case FieldTypes.DATE:
            return DATE_COMPARISONS;
        case FieldTypes.MULTIPLE_CHOICE:
            return field?.properties?.allowMultipleSelection ? MULTI_COMPARISONS : CHOICE_COMPARISONS;
        case FieldTypes.DROP_DOWN:
            return CHOICE_COMPARISONS;
        default:
            return TEXT_COMPARISONS;
    }
}

export const needsValue = (c: Comparison) => c !== Comparison.IS_EMPTY && c !== Comparison.IS_NOT_EMPTY;

export const selectClass = 'text-black-800 focus:border-brand-500 w-full min-w-0 rounded-md border border-black-300 bg-white px-2 py-1.5 text-xs outline-none';

export function newConditionFor(sourceFields: StandardFormFieldDto[]): LogicCondition {
    const first = sourceFields[0];
    return { fieldId: first?.id ?? '', fieldType: first?.type ?? '', comparison: Comparison.IS_EQUAL, value: '' };
}

/** One condition row: [source field] [comparison] [value], with an optional remove button. */
export function ConditionRow({
    condition,
    sourceFields,
    onChange,
    onRemove
}: {
    condition: LogicCondition;
    sourceFields: StandardFormFieldDto[];
    onChange: (patch: Partial<LogicCondition>) => void;
    onRemove?: () => void;
}) {
    const src = sourceFields.find((f) => f.id === condition.fieldId);
    const comparisons = comparisonsForField(src);
    return (
        <div className="border-black-200 bg-new-white-200 relative flex flex-col gap-1.5 rounded-md border p-2">
            {onRemove && (
                <button aria-label="Remove condition" className="text-black-400 hover:text-black-700 absolute right-1.5 top-1.5" onClick={onRemove}>
                    <X className="h-3.5 w-3.5" />
                </button>
            )}
            <select
                className={selectClass}
                value={condition.fieldId}
                onChange={(e) => {
                    const f = sourceFields.find((sf) => sf.id === e.target.value);
                    onChange({ fieldId: e.target.value, fieldType: f?.type ?? '', comparison: comparisonsForField(f)[0], value: '' });
                }}
            >
                {sourceFields.map((f, i) => (
                    <option key={f.id} value={f.id}>
                        {fieldLabel(f, `Question ${i + 1}`)}
                    </option>
                ))}
            </select>
            <select className={selectClass} value={condition.comparison} onChange={(e) => onChange({ comparison: e.target.value as Comparison, value: '' })}>
                {comparisons.map((c) => (
                    <option key={c} value={c}>
                        {COMPARISON_LABELS[c]}
                    </option>
                ))}
            </select>
            {needsValue(condition.comparison) && <ConditionValueInput field={src} value={condition.value} onChange={(v) => onChange({ value: v })} />}
        </div>
    );
}

export function ConditionValueInput({ field, value, onChange }: { field?: StandardFormFieldDto; value: any; onChange: (v: any) => void }) {
    if (field?.type === FieldTypes.YES_NO) {
        return (
            <select className={selectClass} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
                <option value="">Select…</option>
                <option value="Yes">Yes</option>
                <option value="No">No</option>
            </select>
        );
    }
    if (field?.type === FieldTypes.MULTIPLE_CHOICE || field?.type === FieldTypes.DROP_DOWN) {
        const choices = field?.properties?.choices ?? [];
        return (
            <select className={selectClass} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
                <option value="">Select…</option>
                {choices.map((c) => (
                    <option key={c.id} value={c.value ?? c.label ?? ''}>
                        {c.value || c.label || 'Option'}
                    </option>
                ))}
            </select>
        );
    }
    const numeric = field?.type === FieldTypes.NUMBER || field?.type === FieldTypes.RATING || field?.type === FieldTypes.LINEAR_RATING;
    const date = field?.type === FieldTypes.DATE;
    return <input className={selectClass} type={date ? 'date' : numeric ? 'number' : 'text'} value={value ?? ''} placeholder="value" onChange={(e) => onChange(e.target.value)} />;
}
