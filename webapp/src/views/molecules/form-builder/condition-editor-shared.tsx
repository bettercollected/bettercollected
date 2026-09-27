'use client';

import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { Comparison, GroupConditionMode, LogicCondition } from '@app/models/types/form-builder-shared';
import { getGroupChildren, isRepeatingGroup } from '@app/utils/repeating-groups';
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

/**
 * Build labelled sources from slides, adding a "Page N ·" prefix when the form has more than one page.
 * Internal fields are never sources: respondents never answer them, so no
 * respondent logic or pipe may depend on them (the backend refuses it too).
 */
export function buildSourceFields(slides: Array<StandardFormFieldDto>, predicate: (slide: StandardFormFieldDto, slideIndex: number, field: StandardFormFieldDto) => boolean): SourceField[] {
    const multiPage = (slides || []).length > 1;
    const sources: SourceField[] = [];
    (slides || []).forEach((slide, sIdx) => {
        slide?.properties?.fields?.forEach((field) => {
            if (field?.internal || !predicate(slide, sIdx, field)) return;
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

/** Item-count comparisons offered for a repeating group ("number of items is / at least / at most"). */
export const COUNT_COMPARISON_LABELS: Record<string, string> = {
    [Comparison.IS_EQUAL]: 'is',
    [Comparison.GREATER_THAN_EQUAL]: 'is at least',
    [Comparison.LESS_THAN_EQUAL]: 'is at most'
};

export const GROUP_MODE_LABELS: Record<GroupConditionMode, string> = {
    COUNT: 'Number of items',
    ANY: 'Any item',
    ALL: 'All items'
};

/** Group-level condition defaults when a repeating group is picked as the source. */
export function groupConditionFor(group: StandardFormFieldDto, groupMode: GroupConditionMode = 'COUNT'): Partial<LogicCondition> {
    if (groupMode === 'COUNT') return { fieldId: group.id, fieldType: FieldTypes.GROUP, groupMode, comparison: Comparison.GREATER_THAN_EQUAL, value: '', childFieldId: undefined, childFieldType: undefined };
    const child = getGroupChildren(group).find((c) => c.type !== FieldTypes.TEXT);
    return { fieldId: group.id, fieldType: FieldTypes.GROUP, groupMode, childFieldId: child?.id, childFieldType: child?.type, comparison: comparisonsForField(child)[0], value: '' };
}

/** A condition is complete only if it names a field, a comparison, and (when required) a value. */
export function isConditionComplete(c: LogicCondition | undefined): boolean {
    if (!c?.fieldId || !c?.comparison) return false;
    if ((c.groupMode === 'ANY' || c.groupMode === 'ALL') && !c.childFieldId) return false;
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
    const group = isRepeatingGroup(src) ? src : undefined;
    const groupChildren = group ? getGroupChildren(group).filter((c) => c.type !== FieldTypes.TEXT) : [];
    const child = group && condition.groupMode !== 'COUNT' ? groupChildren.find((c) => c.id === condition.childFieldId) : undefined;
    // A group condition compares the item count, or one question in any/all items.
    const valueField: StandardFormFieldDto | undefined = group ? (condition.groupMode === 'COUNT' ? ({ id: 'count', index: 0, type: FieldTypes.NUMBER } as StandardFormFieldDto) : child) : src;
    const comparisons = group && condition.groupMode === 'COUNT' ? (Object.keys(COUNT_COMPARISON_LABELS) as Comparison[]) : comparisonsForField(valueField);
    const labels = group && condition.groupMode === 'COUNT' ? COUNT_COMPARISON_LABELS : COMPARISON_LABELS;
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
                    if (f && isRepeatingGroup(f)) onChange(groupConditionFor(f));
                    else onChange({ fieldId: e.target.value, fieldType: f?.type ?? '', comparison: comparisonsForField(f)[0], value: '', groupMode: undefined, childFieldId: undefined, childFieldType: undefined });
                }}
            >
                {sources.map((s) => (
                    <option key={s.field.id} value={s.field.id}>
                        {s.label}
                    </option>
                ))}
            </select>
            {group && (
                <select aria-label="Group condition" className={selectClass} value={condition.groupMode ?? 'COUNT'} onChange={(e) => onChange(groupConditionFor(group, e.target.value as GroupConditionMode))}>
                    {(Object.keys(GROUP_MODE_LABELS) as GroupConditionMode[]).map((mode) => (
                        <option key={mode} value={mode} disabled={mode !== 'COUNT' && groupChildren.length === 0}>
                            {GROUP_MODE_LABELS[mode]}
                        </option>
                    ))}
                </select>
            )}
            {group && condition.groupMode !== 'COUNT' && (
                <select
                    aria-label="Question in each item"
                    className={selectClass}
                    value={condition.childFieldId ?? ''}
                    onChange={(e) => {
                        const next = groupChildren.find((c) => c.id === e.target.value);
                        onChange({ childFieldId: next?.id, childFieldType: next?.type, comparison: comparisonsForField(next)[0], value: '' });
                    }}
                >
                    {groupChildren.map((c) => (
                        <option key={c.id} value={c.id}>
                            {fieldText(c)}
                        </option>
                    ))}
                </select>
            )}
            <select className={selectClass} value={condition.comparison} onChange={(e) => onChange({ comparison: e.target.value as Comparison, value: '' })}>
                {comparisons.map((c) => (
                    <option key={c} value={c}>
                        {labels[c]}
                    </option>
                ))}
            </select>
            {needsValue(condition.comparison) && <ConditionValueInput field={valueField} value={condition.value} invalid={valueMissing} onChange={(v) => onChange({ value: v })} />}
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
    if (first && isRepeatingGroup(first)) return groupConditionFor(first) as LogicCondition;
    return { fieldId: first?.id ?? '', fieldType: first?.type ?? '', comparison: Comparison.IS_EQUAL, value: '' };
}

/** Condition sources: answerable questions plus repeating groups (conditioned on as a whole). */
export function isConditionSource(field: StandardFormFieldDto): boolean {
    return V2InputFields.includes(field.type) || isRepeatingGroup(field);
}
