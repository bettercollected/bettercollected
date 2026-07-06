'use client';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicCondition } from '@app/models/types/form-builder-shared';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { X } from 'lucide-react';

/** A candidate condition source: the field plus a display label that matches the canvas. */
export interface SourceField {
    field: StandardFormFieldDto;
    label: string;
}

/**
 * Same text the canvas shows for a question (title, else its placeholder), so the
 * logic picker never disagrees with what the creator sees on the page.
 */
export function fieldText(field: StandardFormFieldDto | undefined): string {
    if (!field) return '';
    const t = extractTextfromJSON(field)?.trim();
    return t || 'Untitled question';
}

/** Short, stable-ish page name used wherever logic refers to a page. */
export function pageLabel(slide: StandardFormFieldDto | undefined, index: number): string {
    const first = slide?.properties?.fields?.[0];
    const text = first ? fieldText(first) : '';
    return text ? `Page ${index + 1} · ${text}` : `Page ${index + 1}`;
}

/** Build labelled sources from slides, adding a "Page N ·" prefix when the form has more than one page. */
export function buildSourceFields(slides: Array<StandardFormFieldDto>, predicate: (slide: StandardFormFieldDto, slideIndex: number, field: StandardFormFieldDto) => boolean): SourceField[] {
    const multiPage = (slides || []).length > 1;
    const sources: SourceField[] = [];
    (slides || []).forEach((slide, sIdx) => {
        slide?.properties?.fields?.forEach((field) => {
            if (!predicate(slide, sIdx, field)) return;
            const text = fieldText(field);
            sources.push({ field, label: multiPage ? `Page ${sIdx + 1} · ${text}` : text });
        });
    });
    return sources;
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

/** A condition is complete only if it names a field, a comparison, and (when required) a value. */
export function isConditionComplete(c: LogicCondition | undefined): boolean {
    if (!c?.fieldId || !c?.comparison) return false;
    if (needsValue(c.comparison) && (c.value === undefined || c.value === null || String(c.value).trim() === '')) return false;
    return true;
}

export const selectClass = 'text-black-800 focus:border-brand-500 w-full min-w-0 rounded-md border border-black-300 bg-white px-2 py-1.5 text-xs outline-none';
const invalidSelectClass = selectClass.replace('border-black-300', 'border-amber-400');

/** One condition row: [source field] [comparison] [value], with an optional remove button. */
export function ConditionRow({
    condition,
    sources,
    onChange,
    onRemove
}: {
    condition: LogicCondition;
    sources: SourceField[];
    onChange: (patch: Partial<LogicCondition>) => void;
    onRemove?: () => void;
}) {
    const src = sources.find((s) => s.field.id === condition.fieldId)?.field;
    const comparisons = comparisonsForField(src);
    const valueMissing = needsValue(condition.comparison) && (condition.value === undefined || condition.value === null || String(condition.value).trim() === '');
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
                    const f = sources.find((s) => s.field.id === e.target.value)?.field;
                    onChange({ fieldId: e.target.value, fieldType: f?.type ?? '', comparison: comparisonsForField(f)[0], value: '' });
                }}
            >
                {sources.map((s) => (
                    <option key={s.field.id} value={s.field.id}>
                        {s.label}
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
            {needsValue(condition.comparison) && <ConditionValueInput field={src} value={condition.value} invalid={valueMissing} onChange={(v) => onChange({ value: v })} />}
            {valueMissing && <span className="text-[11px] text-amber-700">Enter a value for this rule to work.</span>}
        </div>
    );
}

export function ConditionValueInput({ field, value, onChange, invalid }: { field?: StandardFormFieldDto; value: any; onChange: (v: any) => void; invalid?: boolean }) {
    const cls = invalid ? invalidSelectClass : selectClass;
    if (field?.type === FieldTypes.YES_NO) {
        return (
            <select className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
                <option value="">Select…</option>
                <option value="Yes">Yes</option>
                <option value="No">No</option>
            </select>
        );
    }
    if (field?.type === FieldTypes.MULTIPLE_CHOICE || field?.type === FieldTypes.DROP_DOWN) {
        const choices = field?.properties?.choices ?? [];
        return (
            <select className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
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
    return <input className={cls} type={date ? 'date' : numeric ? 'number' : 'text'} value={value ?? ''} placeholder="value" onChange={(e) => onChange(e.target.value)} />;
}

export function newConditionFor(sources: SourceField[]): LogicCondition {
    const first = sources[0]?.field;
    return { fieldId: first?.id ?? '', fieldType: first?.type ?? '', comparison: Comparison.IS_EQUAL, value: '' };
}
