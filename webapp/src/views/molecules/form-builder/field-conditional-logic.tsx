'use client';

import { StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { FieldConditionalLogic, LogicalOperator, LogicCondition } from '@app/models/types/form-builder-shared';
import { Switch } from '@app/shadcn/components/ui/switch';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { ConditionRow, newConditionFor, selectClass } from './condition-editor-shared';

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

    const commit = (next: FieldConditionalLogic | undefined) => updateFieldConditionalLogic(activeField.index, activeSlide.index, next);

    const toggle = (on: boolean) => {
        if (on) commit({ action: 'SHOW', operator: LogicalOperator.AND, conditions: [newConditionFor(sourceFields)] });
        else commit(undefined);
    };

    const patchCondition = (idx: number, patch: Partial<LogicCondition>) => {
        if (!logic) return;
        commit({ ...logic, conditions: logic.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)) });
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

                    {logic.conditions.map((condition, idx) => (
                        <ConditionRow
                            key={idx}
                            condition={condition}
                            sourceFields={sourceFields}
                            onChange={(patch) => patchCondition(idx, patch)}
                            onRemove={logic.conditions.length > 1 ? () => commit({ ...logic, conditions: logic.conditions.filter((_, i) => i !== idx) }) : undefined}
                        />
                    ))}

                    <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={() => commit({ ...logic, conditions: [...logic.conditions, newConditionFor(sourceFields)] })}>
                        + Add condition
                    </button>
                </div>
            )}
        </div>
    );
}
