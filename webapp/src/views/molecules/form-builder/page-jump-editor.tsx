'use client';

import { StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator, LogicCondition, PageJump } from '@app/models/types/form-builder-shared';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { X } from 'lucide-react';
import { ConditionRow, newConditionFor, selectClass } from './condition-editor-shared';

export default function PageJumpEditor() {
    const { formFields, activeSlide, updateSlideJumps } = useFormFieldsAtom();

    if (!activeSlide) return null;

    // Conditions can reference any input field answerable by the time the responder
    // leaves this page: everything on this slide and every earlier slide.
    const sourceFields: StandardFormFieldDto[] = [];
    (formFields || []).forEach((slide, sIdx) => {
        if (sIdx > activeSlide.index) return;
        slide?.properties?.fields?.forEach((f) => {
            if (V2InputFields.includes(f.type)) sourceFields.push(f);
        });
    });

    // Jump targets: every other page, plus "submit".
    const targets = [
        ...(formFields || []).map((slide, i) => ({ id: slide.id, label: `Page ${i + 1}` })).filter((_, i) => i !== activeSlide.index),
        { id: JUMP_TARGET_SUBMIT, label: 'Submit form' }
    ];

    const jumps: PageJump[] = (activeSlide?.properties?.jumps as PageJump[] | undefined) ?? [];

    const commit = (next: PageJump[]) => updateSlideJumps(activeSlide.index, next.length ? next : undefined);

    const patchJump = (idx: number, patch: Partial<PageJump>) => commit(jumps.map((j, i) => (i === idx ? { ...j, ...patch } : j)));
    const patchCondition = (jIdx: number, cIdx: number, patch: Partial<LogicCondition>) =>
        patchJump(jIdx, { conditions: jumps[jIdx].conditions.map((c, i) => (i === cIdx ? { ...c, ...patch } : c)) });

    const addJump = () => commit([...jumps, { operator: LogicalOperator.AND, conditions: [newConditionFor(sourceFields)], target: targets[0]?.id ?? JUMP_TARGET_SUBMIT }]);

    if (sourceFields.length === 0) {
        return (
            <div className="flex flex-col gap-1 px-4 py-4">
                <div className="text-black-700 text-xs font-medium">Page logic</div>
                <div className="text-black-500 text-xs">Add questions to this page (or an earlier one) to branch to another page based on the answers.</div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-3 px-4 py-4">
            <div>
                <div className="text-black-700 text-xs font-medium">Page logic</div>
                {jumps.length > 0 && <div className="text-black-500 mt-0.5 text-xs">Checked top to bottom — the first rule that matches wins.</div>}
            </div>

            {jumps.map((jump, jIdx) => (
                <div key={jIdx} className="border-black-300 relative flex flex-col gap-2 rounded-md border p-2">
                    <button aria-label="Remove rule" className="text-black-400 hover:text-black-700 absolute right-1.5 top-1.5" onClick={() => commit(jumps.filter((_, i) => i !== jIdx))}>
                        <X className="h-3.5 w-3.5" />
                    </button>

                    <div className="text-black-600 flex flex-col gap-1.5 text-xs">
                        {jump.conditions.length > 1 ? (
                            <div className="flex items-center gap-1">
                                <span className="shrink-0">When</span>
                                <select className={selectClass} value={jump.operator} onChange={(e) => patchJump(jIdx, { operator: e.target.value as LogicalOperator })}>
                                    <option value={LogicalOperator.AND}>all</option>
                                    <option value={LogicalOperator.OR}>any</option>
                                </select>
                                <span className="shrink-0">match:</span>
                            </div>
                        ) : (
                            <span>When this matches:</span>
                        )}
                    </div>

                    {jump.conditions.map((condition, cIdx) => (
                        <ConditionRow
                            key={cIdx}
                            condition={condition}
                            sourceFields={sourceFields}
                            onChange={(patch) => patchCondition(jIdx, cIdx, patch)}
                            onRemove={jump.conditions.length > 1 ? () => patchJump(jIdx, { conditions: jump.conditions.filter((_, i) => i !== cIdx) }) : undefined}
                        />
                    ))}

                    <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={() => patchJump(jIdx, { conditions: [...jump.conditions, newConditionFor(sourceFields)] })}>
                        + Add condition
                    </button>

                    <div className="text-black-600 flex items-center gap-1 text-xs">
                        <span className="shrink-0">→ go to</span>
                        <select className={selectClass} value={jump.target} onChange={(e) => patchJump(jIdx, { target: e.target.value })}>
                            {targets.map((t) => (
                                <option key={t.id} value={t.id}>
                                    {t.label}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            ))}

            <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={addJump}>
                + Add rule
            </button>
        </div>
    );
}
