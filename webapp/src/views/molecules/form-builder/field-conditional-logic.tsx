'use client';

import { FieldConditionalLogic, LogicalOperator, LogicCondition } from '@app/models/types/form-builder-shared';
import { Switch } from '@app/shadcn/components/ui/switch';
import { useAtomValue } from 'jotai';

import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderFieldsValue, useField, useFieldActions, usePageShell } from '@app/store/jotai/entity-hooks';
import { buildSourceFields, ConditionRow, isConditionSource, newConditionFor, sameSourceFields, selectClass } from './condition-editor-shared';

export default function FieldConditionalLogicEditor() {
    const activeFieldComponent = useAtomValue(activeFieldAtom);
    const activeSlideComponent = useAtomValue(activeSlideAtom);
    // The selected question and its page's own settings only.
    const activeField = useField(activeFieldComponent?.id);
    const activeSlide = usePageShell(activeSlideComponent?.id);
    const { updateFieldLogic } = useFieldActions();
    const slideIndex = activeSlide?.index;
    const fieldIndex = activeField?.index;
    const fieldId = activeField?.id;

    // Fields answerable *before* this one (earlier slide, or earlier in the same slide):
    // derived from the form, so typing elsewhere re-renders this only when they change.
    const sources = useBuilderFieldsValue(
        (formFields) =>
            slideIndex === undefined || fieldIndex === undefined
                ? []
                : buildSourceFields(formFields || [], (_slide, sIdx, field) => {
                      if (sIdx > slideIndex) return false;
                      const isEarlier = sIdx < slideIndex || field.index < fieldIndex;
                      return isEarlier && field.id !== fieldId && isConditionSource(field);
                  }),
        [slideIndex, fieldIndex, fieldId],
        sameSourceFields
    );

    if (!activeField || !activeSlide) return null;

    const logic = activeField?.properties?.logic as FieldConditionalLogic | undefined;
    const enabled = !!logic;

    const commit = (next: FieldConditionalLogic | undefined) => updateFieldLogic(activeField.id, next);

    const toggle = (on: boolean) => {
        if (on) commit({ action: 'SHOW', operator: LogicalOperator.AND, conditions: [newConditionFor(sources)] });
        else commit(undefined);
    };

    const patchCondition = (idx: number, patch: Partial<LogicCondition>) => {
        if (!logic) return;
        commit({ ...logic, conditions: logic.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)) });
    };

    if (sources.length === 0) {
        return (
            <div className="border-black-300 flex flex-col gap-1 border-t pt-4">
                <div className="text-black-700 text-xs font-medium">Logic</div>
                <div className="text-black-600 text-xs">Add a question before this one to show or hide this field based on an earlier answer.</div>
            </div>
        );
    }

    return (
        <div className="border-black-300 flex flex-col gap-3 border-t pt-4">
            <div className="flex w-full items-center justify-between">
                <div>
                    <div className="text-black-700 text-xs font-medium">Logic</div>
                    <div className="text-black-600 text-[11px]">Show or hide this field based on answers</div>
                </div>
                <Switch aria-label="Show or hide this field based on answers" checked={enabled} onCheckedChange={toggle} />
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
                            sources={sources}
                            onChange={(patch) => patchCondition(idx, patch)}
                            onRemove={logic.conditions.length > 1 ? () => commit({ ...logic, conditions: logic.conditions.filter((_, i) => i !== idx) }) : undefined}
                        />
                    ))}

                    <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={() => commit({ ...logic, conditions: [...logic.conditions, newConditionFor(sources)] })}>
                        + Add condition
                    </button>
                </div>
            )}
        </div>
    );
}
