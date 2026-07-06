'use client';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldConditionalLogic, JUMP_TARGET_SUBMIT, LogicCondition, PageJump } from '@app/models/types/form-builder-shared';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { isJumpTargetValid } from '@app/utils/conditional-logic';
import { AlertTriangle } from 'lucide-react';
import { COMPARISON_LABELS, fieldText, pageLabel } from './condition-editor-shared';

export default function LogicOverview({ onClose }: { onClose?: () => void }) {
    const { formFields } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();

    const slides = formFields || [];
    const slideIds = new Set(slides.map((s) => s.id));
    const fieldById = new Map<string, StandardFormFieldDto>();
    slides.forEach((s) => s?.properties?.fields?.forEach((f) => fieldById.set(f.id, f)));
    const pageLabelById = new Map<string, string>();
    slides.forEach((s, i) => pageLabelById.set(s.id, pageLabel(s, i)));

    const conditionText = (c: LogicCondition | undefined) => {
        if (!c) return '';
        const src = fieldText(fieldById.get(c.fieldId || '')) || 'a question';
        const cmp = COMPARISON_LABELS[c.comparison] ?? 'matches';
        const val = c.value !== '' && c.value != null ? ` “${c.value}”` : '';
        return `“${src}” ${cmp}${val}`;
    };
    const moreText = (n: number) => (n > 1 ? ` +${n - 1} more` : '');

    // Field-visibility rules
    const fieldRules: { slideIndex: number; fieldIndex: number; fieldId: string; label: string; logic: FieldConditionalLogic }[] = [];
    slides.forEach((slide, sIdx) =>
        slide?.properties?.fields?.forEach((field, fIdx) => {
            const logic = field?.properties?.logic as FieldConditionalLogic | undefined;
            if (logic?.conditions?.length) fieldRules.push({ slideIndex: sIdx, fieldIndex: fIdx, fieldId: field.id, label: fieldText(field), logic });
        })
    );

    // Page jumps
    const jumpRules: { slideIndex: number; slideId: string; label: string; jump: PageJump; broken: boolean }[] = [];
    slides.forEach((slide, sIdx) =>
        (slide?.properties?.jumps as PageJump[] | undefined)?.forEach((jump) => {
            if (jump?.conditions?.length) jumpRules.push({ slideIndex: sIdx, slideId: slide.id, label: pageLabel(slide, sIdx), jump, broken: !isJumpTargetValid(jump.target, slideIds) });
        })
    );

    const total = fieldRules.length + jumpRules.length;

    const goToField = (r: { slideIndex: number; slideId: string; fieldId: string; fieldIndex: number }) => {
        setActiveSlideComponent({ id: r.slideId, index: r.slideIndex });
        setActiveFieldComponent({ id: r.fieldId, index: r.fieldIndex });
        onClose?.();
    };
    const goToSlide = (slideIndex: number) => {
        setActiveFieldComponent(null);
        setActiveSlideComponent({ id: slides[slideIndex].id, index: slideIndex });
        onClose?.();
    };

    return (
        <div className="shadow-bubble border-black-200 max-h-[70vh] w-[340px] overflow-y-auto rounded-lg border bg-white p-3">
            <div className="text-black-800 mb-1 text-sm font-semibold">Logic</div>
            <p className="text-black-500 mb-3 text-xs">Every show/hide and page-jump rule in this form. Select one to edit it.</p>

            {total === 0 ? (
                <div className="text-black-500 border-black-200 rounded-md border border-dashed px-3 py-4 text-center text-xs">
                    No logic yet. Open a question’s <strong>Logic</strong> section to show/hide it, or a page’s <strong>Logic</strong> section to branch.
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    {jumpRules.length > 0 && (
                        <div className="flex flex-col gap-1">
                            <div className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">Page jumps</div>
                            {jumpRules.map((r, i) => {
                                const target = r.broken ? '⚠ a deleted page' : r.jump.target === JUMP_TARGET_SUBMIT ? 'Submit' : pageLabelById.get(r.jump.target) ?? 'a page';
                                return (
                                    <button key={`j${i}`} onClick={() => goToSlide(r.slideIndex)} className="hover:bg-new-white-200 flex flex-col items-start gap-0.5 rounded-md px-2 py-1.5 text-left">
                                        <span className="text-black-800 flex items-center gap-1 text-xs font-medium">
                                            {r.broken && <AlertTriangle className="h-3 w-3 text-amber-600" />}
                                            On “{r.label}” → {target}
                                        </span>
                                        <span className="text-black-500 text-xs">
                                            when {conditionText(r.jump.conditions[0])}
                                            {moreText(r.jump.conditions.length)}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {fieldRules.length > 0 && (
                        <div className="flex flex-col gap-1">
                            <div className="text-black-400 text-[10px] font-semibold uppercase tracking-wide">Show / hide fields</div>
                            {fieldRules.map((r, i) => (
                                <button key={`f${i}`} onClick={() => goToField({ ...r, slideId: slides[r.slideIndex].id })} className="hover:bg-new-white-200 flex flex-col items-start gap-0.5 rounded-md px-2 py-1.5 text-left">
                                    <span className="text-black-800 text-xs font-medium">
                                        {r.logic.action === 'HIDE' ? 'Hide' : 'Show'} “{r.label}”
                                    </span>
                                    <span className="text-black-500 text-xs">
                                        when {conditionText(r.logic.conditions[0])}
                                        {moreText(r.logic.conditions.length)}
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
