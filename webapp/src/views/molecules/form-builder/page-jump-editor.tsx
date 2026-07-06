'use client';

import { V2InputFields } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator, LogicCondition, PageJump } from '@app/models/types/form-builder-shared';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { isJumpTargetValid } from '@app/utils/conditional-logic';
import { ChevronDown, ChevronUp, X } from 'lucide-react';
import { buildSourceFields, ConditionRow, newConditionFor, pageLabel, selectClass } from './condition-editor-shared';

const MISSING = '__MISSING_TARGET__';

export default function PageJumpEditor() {
    const { formFields, activeSlide, updateSlideJumps } = useFormFieldsAtom();

    if (!activeSlide) return null;

    // Conditions can reference any input field answerable by the time the responder
    // leaves this page: everything on this slide and every earlier slide.
    const sources = buildSourceFields(formFields || [], (_slide, sIdx, field) => sIdx <= activeSlide.index && V2InputFields.includes(field.type));

    // Jump targets: every other page (stable content-derived label), plus "submit".
    const slideIds = new Set((formFields || []).map((s) => s.id));
    const targets = [
        ...(formFields || []).map((slide, i) => ({ id: slide.id, label: pageLabel(slide, i) })).filter((_, i) => i !== activeSlide.index),
        { id: JUMP_TARGET_SUBMIT, label: 'Submit form' }
    ];
    const nextPageId = (formFields || [])[activeSlide.index + 1]?.id;

    const jumps: PageJump[] = (activeSlide?.properties?.jumps as PageJump[] | undefined) ?? [];

    const commit = (next: PageJump[]) => updateSlideJumps(activeSlide.index, next.length ? next : undefined);
    const patchJump = (idx: number, patch: Partial<PageJump>) => commit(jumps.map((j, i) => (i === idx ? { ...j, ...patch } : j)));
    const patchCondition = (jIdx: number, cIdx: number, patch: Partial<LogicCondition>) =>
        patchJump(jIdx, { conditions: jumps[jIdx].conditions.map((c, i) => (i === cIdx ? { ...c, ...patch } : c)) });
    const moveJump = (idx: number, dir: -1 | 1) => {
        const to = idx + dir;
        if (to < 0 || to >= jumps.length) return;
        const next = [...jumps];
        [next[idx], next[to]] = [next[to], next[idx]];
        commit(next);
    };
    const addJump = () => commit([...jumps, { operator: LogicalOperator.AND, conditions: [newConditionFor(sources)], target: targets[0]?.id ?? JUMP_TARGET_SUBMIT }]);

    if (sources.length === 0) {
        return (
            <div className="flex flex-col gap-1 px-4 py-4">
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Logic</div>
                <div className="text-black-500 text-xs">Add questions to this page (or an earlier one) to send people to another page based on their answers.</div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-3 px-4 py-4">
            <div>
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Logic</div>
                <div className="text-black-500 text-[11px]">Send people to another page based on their answers.{jumps.length > 1 ? ' Checked top to bottom — first match wins.' : ''}</div>
            </div>

            {jumps.map((jump, jIdx) => {
                const targetValid = isJumpTargetValid(jump.target, slideIds);
                const isNoOp = targetValid && jump.target === nextPageId;
                return (
                    <div key={jIdx} className="border-black-300 relative flex flex-col gap-2 rounded-md border p-2">
                        <div className="text-black-400 flex items-center gap-1">
                            {jumps.length > 1 && (
                                <>
                                    <span className="text-[11px] font-medium">Rule {jIdx + 1}</span>
                                    <button aria-label="Move rule up" disabled={jIdx === 0} className="hover:text-black-700 disabled:opacity-30" onClick={() => moveJump(jIdx, -1)}>
                                        <ChevronUp className="h-3.5 w-3.5" />
                                    </button>
                                    <button aria-label="Move rule down" disabled={jIdx === jumps.length - 1} className="hover:text-black-700 disabled:opacity-30" onClick={() => moveJump(jIdx, 1)}>
                                        <ChevronDown className="h-3.5 w-3.5" />
                                    </button>
                                </>
                            )}
                            <button aria-label="Remove rule" className="hover:text-black-700 ml-auto" onClick={() => commit(jumps.filter((_, i) => i !== jIdx))}>
                                <X className="h-3.5 w-3.5" />
                            </button>
                        </div>

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
                                sources={sources}
                                onChange={(patch) => patchCondition(jIdx, cIdx, patch)}
                                onRemove={jump.conditions.length > 1 ? () => patchJump(jIdx, { conditions: jump.conditions.filter((_, i) => i !== cIdx) }) : undefined}
                            />
                        ))}

                        <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={() => patchJump(jIdx, { conditions: [...jump.conditions, newConditionFor(sources)] })}>
                            + Add condition
                        </button>

                        <div className="text-black-600 flex items-center gap-1 text-xs">
                            <span className="shrink-0">→ go to</span>
                            <select
                                className={targetValid ? selectClass : selectClass.replace('border-black-300', 'border-amber-400')}
                                value={targetValid ? jump.target : MISSING}
                                onChange={(e) => patchJump(jIdx, { target: e.target.value })}
                            >
                                {!targetValid && <option value={MISSING}>⚠ Deleted page — pick a target</option>}
                                {targets.map((t) => (
                                    <option key={t.id} value={t.id}>
                                        {t.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        {!targetValid && <span className="text-[11px] text-amber-700">This rule points to a page that was deleted. Pick a new destination.</span>}
                        {isNoOp && <span className="text-black-500 text-[11px]">This is already the next page, so the rule has no effect.</span>}
                    </div>
                );
            })}

            <button className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium" onClick={addJump}>
                + Add rule
            </button>
        </div>
    );
}
