'use client';

import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { Comparison, FieldConditionalLogic, LogicalOperator, LogicCondition } from '@app/models/types/form-builder-shared';
import { Switch } from '@app/shadcn/components/ui/switch';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { X } from 'lucide-react';

// Plain-text label from a field's Tiptap-JSON (or string) title, for the source picker.
function fieldLabel(field: StandardFormFieldDto, fallback: string): string {
    const t: any = field?.title ?? field?.value;
    if (typeof t === 'string' && t.trim()) return t.trim();
    const walk = (node: any): string => {
        if (!node) return '';
        if (typeof node.text === 'string') return node.text;
        if (Array.isArray(node.content)) return node.content.map(walk).join('');
        return '';
    };
    const text = walk(t).trim();
    return text || fallback;
}

const COMPARISON_LABELS: Record<string, string> = {
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

function comparisonsForField(field?: StandardFormFieldDto): Comparison[] {
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

const needsValue = (c: Comparison) => c !== Comparison.IS_EMPTY && c !== Comparison.IS_NOT_EMPTY;

const selectClass = 'text-black-800 focus:border-brand-500 w-full min-w-0 rounded-md border border-black-300 bg-white px-2 py-1.5 text-xs outline-none';

export default function FieldConditionalLogicEditor() {
    const { formFields, activeSlide, activeField, updateFieldConditionalLogic } = useFormFieldsAtom();

    if (!activeField || !activeSlide) return null;

    // Fields answerable *before* this one (earlier slide, or earlier in the same slide).
    const sourceFields: StandardFormFieldDto[] = [];
    (formFields || []).forEach((slide, sIdx) => {
        if (sIdx > activeSlide.index) return;
        slide?.properties?.fields?.forEach((f) => {
            const isEarlier = sIdx < activeSlide.index || f.index < activeField.index;
            if (isEarlier && f.id !== activeField.id && V2InputFields.includes(f.type)) sourceFields.push(f);
        });
    });

    const logic = activeField?.properties?.logic as FieldConditionalLogic | undefined;
    const enabled = !!logic;

    const sourceById = (id: string) => sourceFields.find((f) => f.id === id);

    const commit = (next: FieldConditionalLogic | undefined) => updateFieldConditionalLogic(activeField.index, activeSlide.index, next);

    const newCondition = (): LogicCondition => {
        const first = sourceFields[0];
        return { fieldId: first?.id ?? '', fieldType: first?.type ?? '', comparison: Comparison.IS_EQUAL, value: '' };
    };

    const toggle = (on: boolean) => {
        if (on) commit({ action: 'SHOW', operator: LogicalOperator.AND, conditions: [newCondition()] });
        else commit(undefined);
    };

    const patchCondition = (idx: number, patch: Partial<LogicCondition>) => {
        if (!logic) return;
        const conditions = logic.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c));
        commit({ ...logic, conditions });
    };

    if (sourceFields.length === 0) {
        return (
            <div className="border-black-200 flex flex-col gap-1 border-t pt-4">
                <div className="text-black-700 text-xs font-medium">Logic</div>
                <div className="text-black-500 text-xs">Add a question before this one to show or hide it based on an earlier answer.</div>
            </div>
        );
    }

    return (
        <div className="border-black-200 flex flex-col gap-3 border-t pt-4">
            <div className="flex w-full items-center justify-between">
                <div className="text-black-700 text-xs font-medium">Conditional visibility</div>
                <Switch checked={enabled} onCheckedChange={toggle} />
            </div>

            {enabled && logic && (
                <div className="flex flex-col gap-3">
                    <div className="text-black-600 flex flex-col gap-1.5 text-xs">
                        <select className={selectClass} value={logic.action} onChange={(e) => commit({ ...logic, action: e.target.value as any })}>
                            <option value="SHOW">Show this field when…</option>
                            <option value="HIDE">Hide this field when…</option>
                        </select>
                        {logic.conditions.length > 1 && (
                            <div className="flex items-center gap-1">
                                <span className="shrink-0">Match</span>
                                <select className={selectClass} value={logic.operator} onChange={(e) => commit({ ...logic, operator: e.target.value as LogicalOperator })}>
                                    <option value={LogicalOperator.AND}>all</option>
                                    <option value={LogicalOperator.OR}>any</option>
                                </select>
                                <span className="shrink-0">of these:</span>
                            </div>
                        )}
                    </div>

                    {logic.conditions.map((condition, idx) => {
                        const src = sourceById(condition.fieldId);
                        const comparisons = comparisonsForField(src);
                        const showValue = needsValue(condition.comparison);
                        return (
                            <div key={idx} className="border-black-200 bg-new-white-200 relative flex flex-col gap-1.5 rounded-md border p-2">
                                {logic.conditions.length > 1 && (
                                    <button
                                        aria-label="Remove condition"
                                        className="text-black-400 hover:text-black-700 absolute right-1.5 top-1.5"
                                        onClick={() => commit({ ...logic, conditions: logic.conditions.filter((_, i) => i !== idx) })}
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                )}
                                <select
                                    className={selectClass}
                                    value={condition.fieldId}
                                    onChange={(e) => {
                                        const f = sourceById(e.target.value);
                                        patchCondition(idx, { fieldId: e.target.value, fieldType: f?.type ?? '', comparison: comparisonsForField(f)[0], value: '' });
                                    }}
                                >
                                    {sourceFields.map((f, i) => (
                                        <option key={f.id} value={f.id}>
                                            {fieldLabel(f, `Question ${i + 1}`)}
                                        </option>
                                    ))}
                                </select>
                                <select className={selectClass} value={condition.comparison} onChange={(e) => patchCondition(idx, { comparison: e.target.value as Comparison, value: '' })}>
                                    {comparisons.map((c) => (
                                        <option key={c} value={c}>
                                            {COMPARISON_LABELS[c]}
                                        </option>
                                    ))}
                                </select>
                                {showValue && <ConditionValueInput field={src} value={condition.value} onChange={(v) => patchCondition(idx, { value: v })} />}
                            </div>
                        );
                    })}

                    <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={() => commit({ ...logic, conditions: [...logic.conditions, newCondition()] })}>
                        + Add condition
                    </button>
                </div>
            )}
        </div>
    );
}

function ConditionValueInput({ field, value, onChange }: { field?: StandardFormFieldDto; value: any; onChange: (v: any) => void }) {
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
