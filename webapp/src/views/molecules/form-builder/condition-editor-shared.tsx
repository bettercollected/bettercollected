'use client';

import { useId } from 'react';

import { X } from 'lucide-react';
import i18n from 'i18next';
import { useTranslation } from 'react-i18next';

import { jsonEqual } from '@app/lib/form-ops/model';
import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { Comparison, GroupConditionMode, LogicCondition } from '@app/models/types/form-builder-shared';
import { getGroupChildren, isRepeatingGroup } from '@app/utils/repeating-groups';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

/** A candidate condition source: the field plus a display label that matches the canvas. */
export interface SourceField {
    field: StandardFormFieldDto;
    label: string;
}

/** The same sources: labels, and questions with the same content (for derived values that re-render only on change). */
export const sameSourceFields = (a: SourceField[], b: SourceField[]) => a.length === b.length && a.every((source, i) => source.label === b[i].label && (source.field === b[i].field || jsonEqual(source.field, b[i].field)));

/**
 * Same text the canvas shows for a question (title, else its placeholder), so the
 * logic picker never disagrees with what the creator sees on the page.
 */
export function fieldText(field: StandardFormFieldDto | undefined, lng?: string): string {
    if (!field) return '';
    const t = extractTextfromJSON(field)?.trim();
    return t || i18n.t('builder:INSPECTOR.UNTITLED', { lng });
}

/** Short, stable-ish page name used wherever logic refers to a page. */
export function pageLabel(slide: StandardFormFieldDto | undefined, index: number): string {
    const first = slide?.properties?.fields?.[0];
    const text = first ? fieldText(first) : '';
    return text ? i18n.t('builder:OUTLINE.PAGE_PREFIX', { n: index + 1 }) + text : i18n.t('builder:OUTLINE.PAGE_N', { n: index + 1 });
}

/** A page's name without the "Page n ·" prefix: the text of its first question, or "Page n" for a page without questions. */
export function pageTitleOnly(slide: StandardFormFieldDto | undefined, index: number): string {
    const first = slide?.properties?.fields?.[0];
    return first ? fieldText(first) : i18n.t('builder:OUTLINE.PAGE_N', { n: index + 1 });
}

/**
 * Build labelled sources from slides, adding a "Page N ·" prefix when the form has more than one page.
 * `lng` fixes the language of that prefix and of the untitled fallback (a label that is stored in the form is
 * made in English, whatever language the creator works in).
 * Internal fields are never sources: respondents never answer them, so no
 * respondent logic or pipe may depend on them (the backend refuses it too).
 */
export function buildSourceFields(slides: Array<StandardFormFieldDto>, predicate: (slide: StandardFormFieldDto, slideIndex: number, field: StandardFormFieldDto) => boolean, lng?: string): SourceField[] {
    const multiPage = (slides || []).length > 1;
    const sources: SourceField[] = [];
    (slides || []).forEach((slide, sIdx) => {
        slide?.properties?.fields?.forEach((field) => {
            if (field?.internal || !predicate(slide, sIdx, field)) return;
            const text = fieldText(field, lng);
            sources.push({ field, label: multiPage ? i18n.t('builder:OUTLINE.PAGE_PREFIX', { n: sIdx + 1, lng }) + text : text });
        });
    });
    return sources;
}

const TEXT_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.CONTAINS, Comparison.DOES_NOT_CONTAIN, Comparison.STARTS_WITH, Comparison.ENDS_WITH, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const NUMBER_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.GREATER_THAN, Comparison.GREATER_THAN_EQUAL, Comparison.LESS_THAN, Comparison.LESS_THAN_EQUAL, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const CHOICE_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const MULTI_COMPARISONS = [Comparison.CONTAINS, Comparison.DOES_NOT_CONTAIN, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const DATE_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.GREATER_THAN, Comparison.GREATER_THAN_EQUAL, Comparison.LESS_THAN, Comparison.LESS_THAN_EQUAL, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const BOOL_COMPARISONS = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL];
// An address is asked about its postcode, as text (backend ADDRESS_COMPARISONS).
const ADDRESS_LIST = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.STARTS_WITH, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const SIGNED_COMPARISONS = [Comparison.IS_NOT_EMPTY, Comparison.IS_EMPTY];
// A date range includes a day, does not include it, starts after it or ends before it (compareDateRange); tags are asked like a multi-select.
const RANGE_COMPARISONS = [Comparison.CONTAINS, Comparison.DOES_NOT_CONTAIN, Comparison.GREATER_THAN, Comparison.LESS_THAN, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];

export function comparisonsForField(field?: StandardFormFieldDto): Comparison[] {
    switch (field?.type) {
        case FieldTypes.YES_NO:
            return BOOL_COMPARISONS;
        case FieldTypes.NUMBER:
        case FieldTypes.RATING:
        case FieldTypes.LINEAR_RATING:
        case FieldTypes.CURRENCY:
            return NUMBER_COMPARISONS;
        case FieldTypes.CALCULATED:
            // a number, a yes/no or a text: every comparison applies
            return [...new Set([...NUMBER_COMPARISONS, ...TEXT_COMPARISONS])];
        case FieldTypes.DATE:
        case FieldTypes.DAY:
        case FieldTypes.TIME:
            return DATE_COMPARISONS;
        case FieldTypes.DATE_RANGE:
            return RANGE_COMPARISONS;
        case FieldTypes.TAGS:
            return MULTI_COMPARISONS;
        case FieldTypes.ADDRESS:
            return ADDRESS_LIST;
        case FieldTypes.SIGNATURE:
            // signed or not: nothing else can be asked of a signature
            return SIGNED_COMPARISONS;
        case FieldTypes.MULTIPLE_CHOICE:
            // options from a list or another form's answers have no values to name: only "is it answered"
            if (field?.properties?.optionSource) return SIGNED_COMPARISONS;
            return field?.properties?.allowMultipleSelection ? MULTI_COMPARISONS : CHOICE_COMPARISONS;
        case FieldTypes.DROP_DOWN:
            if (field?.properties?.optionSource) return SIGNED_COMPARISONS;
            return CHOICE_COMPARISONS;
        default:
            return TEXT_COMPARISONS;
    }
}

export const needsValue = (c: Comparison) => c !== Comparison.IS_EMPTY && c !== Comparison.IS_NOT_EMPTY;

/** Item-count comparisons offered for a repeating group ("number of items is / at least / at most"); their words are CONDITION.COUNT_COMPARISON.* in the catalogue. */
export const COUNT_COMPARISONS = [Comparison.IS_EQUAL, Comparison.GREATER_THAN_EQUAL, Comparison.LESS_THAN_EQUAL];

/** The ways to condition on a repeating group; their words are CONDITION.GROUP_MODE.* in the catalogue. */
export const GROUP_MODES: GroupConditionMode[] = ['COUNT', 'ANY', 'ALL'];

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

export const selectClass = 'text-black-800 focus:border-brand-500 w-full min-w-0 rounded-md border border-control bg-white px-2 py-1.5 text-xs outline-hidden';
const invalidSelectClass = selectClass.replace('border-control', 'border-amber-400');

/** One condition row: [source field] [comparison] [value], with an optional remove button. */
export function ConditionRow({ condition, sources, onChange, onRemove }: { condition: LogicCondition; sources: SourceField[]; onChange: (patch: Partial<LogicCondition>) => void; onRemove?: () => void }) {
    const { t } = useTranslation('builder');
    const errorId = useId();
    const src = sources.find((s) => s.field.id === condition.fieldId)?.field;
    const group = isRepeatingGroup(src) ? src : undefined;
    const groupChildren = group ? getGroupChildren(group).filter((c) => c.type !== FieldTypes.TEXT) : [];
    const child = group && condition.groupMode !== 'COUNT' ? groupChildren.find((c) => c.id === condition.childFieldId) : undefined;
    // A group condition compares the item count, or one question in any/all items.
    const valueField: StandardFormFieldDto | undefined = group ? (condition.groupMode === 'COUNT' ? ({ id: 'count', index: 0, type: FieldTypes.NUMBER } as StandardFormFieldDto) : child) : src;
    const counting = !!group && condition.groupMode === 'COUNT';
    const comparisons = counting ? COUNT_COMPARISONS : comparisonsForField(valueField);
    // a date range reads "includes", "starts after", "ends before"
    const ranging = valueField?.type === FieldTypes.DATE_RANGE;
    const comparisonText = (c: Comparison) => t(counting ? `CONDITION.COUNT_COMPARISON.${c}` : ranging ? `CONDITION.RANGE_COMPARISON.${c}` : `CONDITION.COMPARISON.${c}`);
    const valueMissing = needsValue(condition.comparison) && (condition.value === undefined || condition.value === null || String(condition.value).trim() === '');
    return (
        <div className="relative flex flex-col gap-1.5 rounded-md border border-black-300 bg-black-100 p-2">
            {onRemove && (
                <button type="button" aria-label={t('CONDITION.REMOVE')} className="absolute top-1.5 right-1.5 text-black-600 hover:text-black-700" onClick={onRemove}>
                    <X className="h-3.5 w-3.5" />
                </button>
            )}
            <select
                aria-label={t('CONDITION.QUESTION')}
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
                <select aria-label={t('CONDITION.GROUP_CONDITION')} className={selectClass} value={condition.groupMode ?? 'COUNT'} onChange={(e) => onChange(groupConditionFor(group, e.target.value as GroupConditionMode))}>
                    {GROUP_MODES.map((mode) => (
                        <option key={mode} value={mode} disabled={mode !== 'COUNT' && groupChildren.length === 0}>
                            {t(`CONDITION.GROUP_MODE.${mode}`)}
                        </option>
                    ))}
                </select>
            )}
            {group && condition.groupMode !== 'COUNT' && (
                <select
                    aria-label={t('CONDITION.CHILD_QUESTION')}
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
            <select aria-label={t('CONDITION.COMPARISON_LABEL')} className={selectClass} value={condition.comparison} onChange={(e) => onChange({ comparison: e.target.value as Comparison, value: '' })}>
                {comparisons.map((c) => (
                    <option key={c} value={c}>
                        {comparisonText(c)}
                    </option>
                ))}
            </select>
            {needsValue(condition.comparison) && <ConditionValueInput field={valueField} value={condition.value} invalid={valueMissing} describedBy={valueMissing ? errorId : undefined} onChange={(v) => onChange({ value: v })} />}
            {valueMissing && (
                <span id={errorId} className="text-[11px] text-amber-700">
                    {t('CONDITION.VALUE_MISSING')}
                </span>
            )}
        </div>
    );
}

export function ConditionValueInput({ field, value, onChange, invalid, describedBy }: { field?: StandardFormFieldDto; value: any; onChange: (v: any) => void; invalid?: boolean; describedBy?: string }) {
    const { t } = useTranslation('builder');
    const cls = invalid ? invalidSelectClass : selectClass;
    // an input that waits for a value says so to assistive technology too, and points at the reason
    const state = { 'aria-label': t('CONDITION.VALUE'), 'aria-invalid': invalid || undefined, 'aria-describedby': describedBy };
    if (field?.type === FieldTypes.YES_NO) {
        // (the stored values are "Yes" and "No", whatever the language of the labels)
        return (
            <select {...state} className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
                <option value="">{t('CONDITION.SELECT')}</option>
                <option value="Yes">{t('CONDITION.YES')}</option>
                <option value="No">{t('CONDITION.NO')}</option>
            </select>
        );
    }
    if (field?.type === FieldTypes.MULTIPLE_CHOICE || field?.type === FieldTypes.DROP_DOWN) {
        const choices = field?.properties?.choices ?? [];
        return (
            <select {...state} className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
                <option value="">{t('CONDITION.SELECT')}</option>
                {choices.map((c) => (
                    <option key={c.id} value={c.value ?? c.label ?? ''}>
                        {c.value || c.label || t('CONDITION.OPTION')}
                    </option>
                ))}
            </select>
        );
    }
    const numeric = field?.type === FieldTypes.NUMBER || field?.type === FieldTypes.RATING || field?.type === FieldTypes.LINEAR_RATING || field?.type === FieldTypes.CURRENCY;
    // a date range is asked about a day
    const date = field?.type === FieldTypes.DATE || field?.type === FieldTypes.DAY || field?.type === FieldTypes.DATE_RANGE;
    const time = field?.type === FieldTypes.TIME;
    // An amount may have cents: the number box must not insist on whole steps.
    return (
        <input
            {...state}
            className={cls}
            type={date ? 'date' : time ? 'time' : numeric ? 'number' : 'text'}
            step={field?.type === FieldTypes.CURRENCY ? 'any' : undefined}
            value={value ?? ''}
            placeholder={t('CONDITION.VALUE_PLACEHOLDER')}
            onChange={(e) => onChange(e.target.value)}
        />
    );
}

export function newConditionFor(sources: SourceField[]): LogicCondition {
    const first = sources[0]?.field;
    if (first && isRepeatingGroup(first)) return groupConditionFor(first) as LogicCondition;
    // a date range or tags question is not asked "is equal to": its own first comparison
    const comparison = first?.type === FieldTypes.DATE_RANGE || first?.type === FieldTypes.TAGS || first?.type === FieldTypes.SIGNATURE ? comparisonsForField(first)[0] : Comparison.IS_EQUAL;
    return { fieldId: first?.id ?? '', fieldType: first?.type ?? '', comparison, value: '' };
}

/** Condition sources: answerable questions plus repeating groups (conditioned on as a whole). */
export function isConditionSource(field: StandardFormFieldDto): boolean {
    return V2InputFields.includes(field.type) || isRepeatingGroup(field) || field.type === FieldTypes.CALCULATED;
}
