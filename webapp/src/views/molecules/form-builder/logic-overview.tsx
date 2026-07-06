'use client';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, FieldConditionalLogic } from '@app/models/types/form-builder-shared';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';

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

function fieldLabel(field: StandardFormFieldDto | undefined, fallback: string): string {
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

interface LogicRule {
    slideIndex: number;
    fieldIndex: number;
    fieldId: string;
    label: string;
    logic: FieldConditionalLogic;
}

export default function LogicOverview({ onClose }: { onClose?: () => void }) {
    const { formFields } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();

    const byId = new Map<string, { field: StandardFormFieldDto; index: number }>();
    (formFields || []).forEach((slide) => slide?.properties?.fields?.forEach((f, i) => byId.set(f.id, { field: f, index: i })));

    const rules: LogicRule[] = [];
    (formFields || []).forEach((slide, sIdx) =>
        slide?.properties?.fields?.forEach((field, fIdx) => {
            const logic = field?.properties?.logic as FieldConditionalLogic | undefined;
            if (logic?.conditions?.length) {
                rules.push({ slideIndex: sIdx, fieldIndex: fIdx, fieldId: field.id, label: fieldLabel(field, `Question ${fIdx + 1}`), logic });
            }
        })
    );

    const jumpTo = (rule: LogicRule) => {
        setActiveSlideComponent({ id: formFields![rule.slideIndex].id, index: rule.slideIndex });
        setActiveFieldComponent({ id: rule.fieldId, index: rule.fieldIndex });
        onClose?.();
    };

    return (
        <div className="shadow-bubble w-[320px] rounded-lg border border-black-200 bg-white p-3">
            <div className="text-black-800 mb-1 text-sm font-semibold">Logic</div>
            <p className="text-black-500 mb-3 text-xs">Select a question and open its “Conditional visibility” section to show or hide it based on an earlier answer.</p>
            {rules.length === 0 ? (
                <div className="text-black-500 border-black-200 rounded-md border border-dashed px-3 py-4 text-center text-xs">No logic rules yet.</div>
            ) : (
                <div className="flex flex-col gap-1">
                    {rules.map((rule) => {
                        const first = rule.logic.conditions[0];
                        const src = first ? byId.get(first.fieldId)?.field : undefined;
                        const extra = rule.logic.conditions.length - 1;
                        return (
                            <button key={rule.fieldId} onClick={() => jumpTo(rule)} className="hover:bg-new-white-200 flex flex-col items-start gap-0.5 rounded-md px-2 py-1.5 text-left">
                                <span className="text-black-800 text-xs font-medium">
                                    {rule.logic.action === 'HIDE' ? 'Hide' : 'Show'} “{rule.label}”
                                </span>
                                <span className="text-black-500 text-xs">
                                    when “{fieldLabel(src, 'a question')}” {COMPARISON_LABELS[first?.comparison] ?? 'matches'}
                                    {first && first.value !== '' && first.value != null ? ` “${first.value}”` : ''}
                                    {extra > 0 ? ` +${extra} more` : ''}
                                </span>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
