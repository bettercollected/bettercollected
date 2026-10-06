'use client';

import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldConditionalLogic, LogicalOperator } from '@app/models/types/form-builder-shared';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { getGroupChildren, getRepeatSettings, newGroupChild, REPEAT_CHILD_FIELD_TYPES } from '@app/utils/repeating-groups';
import { buildSourceFields, ConditionRow, fieldText, isConditionSource, newConditionFor, SourceField } from '@app/views/molecules/form-builder/condition-editor-shared';
import DateFieldSettings from '@app/views/molecules/form-builder/date-field-settings';
import { getDateRuleSources } from '@app/utils/date-rules';
import { asksForIdentity, WHY_WE_ASK_MAX_LENGTH } from '@app/utils/publish-checks';

const CHILD_TYPES = REPEAT_CHILD_FIELD_TYPES.map((type) => ({ type, name: type === FieldTypes.TEXT ? 'Statement' : (formFieldsList.find((f) => f.type === type)?.name ?? type.replaceAll('_', ' ')) }));
const CHOICE_TYPES: string[] = [FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN];
const PLACEHOLDER_TYPES: string[] = [FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT, FieldTypes.EMAIL, FieldTypes.NUMBER, FieldTypes.LINK, FieldTypes.PHONE_NUMBER];

const inputClass = 'text-black-800 focus:border-brand-500 w-full min-w-0 rounded-md border border-black-300 bg-white px-2 py-1.5 text-sm outline-none';
const iconButton = 'text-black-600 hover:bg-black-100 rounded p-1 disabled:opacity-30';

/**
 * Builder canvas for a repeating group: the group's questions as an editable
 * list — title, type, required, placeholder/choices, a visibility rule on
 * earlier answers of the same item, reorder and remove — plus "add question".
 * Limits and labels live in the settings panel (RepeatingGroupSettings).
 */
export default function RepeatingGroupBuilder({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled?: boolean }) {
    const { formFields, updateGroupChildren } = useFormFieldsAtom();
    const children = getGroupChildren(field);
    const { itemLabel, minItems, maxItems } = getRepeatSettings(field);

    const commit = (next: StandardFormFieldDto[]) => updateGroupChildren(slide.index, field.id, next);
    const patchChild = (id: string, patch: Partial<StandardFormFieldDto>) => commit(children.map((child) => (child.id === id ? { ...child, ...patch } : child)));
    const patchProps = (child: StandardFormFieldDto, patch: Record<string, any>) => patchChild(child.id, { properties: { ...(child.properties || {}), ...patch } });
    const move = (index: number, delta: number) => {
        const next = [...children];
        const [moved] = next.splice(index, 1);
        next.splice(index + delta, 0, moved);
        commit(next);
    };

    // Rules inside an item may use the item's earlier questions (same item)
    // and any question answered before the group.
    const outerSources = buildSourceFields(formFields || [], (_s, sIdx, f) => (sIdx < slide.index || (sIdx === slide.index && f.index < field.index)) && isConditionSource(f));
    const sourcesFor = (index: number): SourceField[] => [
        ...children
            .slice(0, index)
            .filter((c) => c.type !== FieldTypes.TEXT)
            .map((c) => ({ field: c, label: `This ${itemLabel.toLowerCase()} · ${fieldText(c)}` })),
        ...outerSources
    ];

    if (disabled) {
        return (
            <div className="border-black-300 flex w-full flex-col gap-2 rounded-lg border border-dashed p-3 text-sm">
                <span className="text-black-600 text-xs font-semibold uppercase tracking-wide">
                    {itemLabel} · {minItems}–{maxItems}
                </span>
                {children.map((child) => (
                    <span key={child.id} className="text-black-800">
                        {fieldText(child)}
                    </span>
                ))}
            </div>
        );
    }

    return (
        <div className="border-black-300 flex w-full flex-col gap-3 rounded-xl border border-dashed bg-white/60 p-3" onClick={(e) => e.stopPropagation()}>
            <div className="text-black-600 flex items-center justify-between text-xs">
                <span className="font-semibold uppercase tracking-wide">
                    Asked for each {itemLabel.toLowerCase()} · {minItems === maxItems ? maxItems : `${minItems}–${maxItems}`} times
                </span>
            </div>
            {children.length === 0 && <p className="text-black-600 text-sm">Add the questions to ask for each {itemLabel.toLowerCase()}.</p>}
            {children.map((child, index) => {
                const logic = child.properties?.logic as FieldConditionalLogic | undefined;
                const sources = sourcesFor(index);
                return (
                    <div key={child.id} className="border-black-200 flex flex-col gap-2 rounded-lg border bg-white p-3" data-testid="group-child">
                        <div className="flex items-center gap-2">
                            <input
                                key={`${child.id}-${typeof child.title === 'string' ? child.title : ''}`}
                                aria-label="Question"
                                className={inputClass}
                                placeholder="Question"
                                defaultValue={typeof child.title === 'string' ? child.title : fieldText(child)}
                                onBlur={(e) => e.target.value !== child.title && patchChild(child.id, { title: e.target.value })}
                            />
                            <select
                                aria-label="Question type"
                                className={`${inputClass} w-36 shrink-0`}
                                value={child.type}
                                onChange={(e) => {
                                    const fresh = newGroupChild(e.target.value, index);
                                    patchChild(child.id, { type: e.target.value, properties: { ...fresh.properties, placeholder: child.properties?.placeholder, logic: child.properties?.logic } });
                                }}
                            >
                                {CHILD_TYPES.map((option) => (
                                    <option key={option.type} value={option.type}>
                                        {option.name}
                                    </option>
                                ))}
                            </select>
                            <button type="button" className={iconButton} aria-label="Move question up" disabled={index === 0} onClick={() => move(index, -1)}>
                                <ArrowUp className="h-4 w-4" />
                            </button>
                            <button type="button" className={iconButton} aria-label="Move question down" disabled={index === children.length - 1} onClick={() => move(index, 1)}>
                                <ArrowDown className="h-4 w-4" />
                            </button>
                            <button type="button" className="rounded p-1 text-[#C43D3D] hover:bg-[#FBEFEF]" aria-label="Remove question" onClick={() => commit(children.filter((c) => c.id !== child.id))}>
                                <Trash2 className="h-4 w-4" />
                            </button>
                        </div>
                        <div className="text-black-700 flex flex-wrap items-center gap-4 text-xs">
                            {child.type !== FieldTypes.TEXT && (
                                <label className="flex items-center gap-1.5">
                                    <input type="checkbox" checked={!!child.validations?.required} onChange={(e) => patchChild(child.id, { validations: { ...(child.validations || {}), required: e.target.checked } })} />
                                    Required in each {itemLabel.toLowerCase()}
                                </label>
                            )}
                            {PLACEHOLDER_TYPES.includes(child.type) && (
                                <input
                                    key={`${child.id}-placeholder-${child.properties?.placeholder ?? ''}`}
                                    aria-label="Placeholder"
                                    className={`${inputClass} w-48 text-xs`}
                                    placeholder="Placeholder (optional)"
                                    defaultValue={child.properties?.placeholder ?? ''}
                                    onBlur={(e) => e.target.value !== (child.properties?.placeholder ?? '') && patchProps(child, { placeholder: e.target.value })}
                                />
                            )}
                            {(asksForIdentity(child) || !!child.properties?.whyWeAsk) && (
                                <input
                                    key={`${child.id}-why-${child.properties?.whyWeAsk ?? ''}`}
                                    aria-label="Why we ask this"
                                    className={`${inputClass} w-full text-xs ${child.properties?.whyWeAsk?.trim() ? '' : 'border-amber-500'}`}
                                    placeholder="Why we ask this (needed to publish)"
                                    maxLength={WHY_WE_ASK_MAX_LENGTH}
                                    defaultValue={child.properties?.whyWeAsk ?? ''}
                                    onBlur={(e) => e.target.value !== (child.properties?.whyWeAsk ?? '') && patchProps(child, { whyWeAsk: e.target.value })}
                                />
                            )}
                            {child.type !== FieldTypes.TEXT && sources.length > 0 && (
                                <label className="flex items-center gap-1.5">
                                    <input
                                        type="checkbox"
                                        checked={!!logic}
                                        onChange={(e) => patchProps(child, { logic: e.target.checked ? { action: 'SHOW', operator: LogicalOperator.AND, conditions: [newConditionFor(sources)] } : undefined })}
                                    />
                                    Show only when…
                                </label>
                            )}
                        </div>
                        {CHOICE_TYPES.includes(child.type) && (
                            <div className="flex flex-col gap-1">
                                {(child.properties?.choices ?? []).map((choice, choiceIndex) => (
                                    <div key={choice.id} className="flex items-center gap-2">
                                        <input
                                            key={`${choice.id}-${choice.value ?? ''}`}
                                            aria-label={`Option ${choiceIndex + 1}`}
                                            className={`${inputClass} text-xs`}
                                            defaultValue={choice.value ?? ''}
                                            onBlur={(e) =>
                                                e.target.value !== choice.value && patchProps(child, { choices: (child.properties?.choices ?? []).map((c) => (c.id === choice.id ? { ...c, value: e.target.value } : c)) })
                                            }
                                        />
                                        <button
                                            type="button"
                                            className={iconButton}
                                            aria-label={`Remove option ${choiceIndex + 1}`}
                                            disabled={(child.properties?.choices?.length ?? 0) <= 2}
                                            onClick={() => patchProps(child, { choices: (child.properties?.choices ?? []).filter((c) => c.id !== choice.id) })}
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                ))}
                                <button
                                    type="button"
                                    className="text-brand-500 hover:text-brand-600 w-fit text-xs font-medium"
                                    onClick={() => {
                                        const extra = newGroupChild(FieldTypes.MULTIPLE_CHOICE, 0).properties!.choices![0];
                                        patchProps(child, { choices: [...(child.properties?.choices ?? []), { ...extra, value: `Option ${(child.properties?.choices?.length ?? 0) + 1}` }] });
                                    }}
                                >
                                    + Add option
                                </button>
                            </div>
                        )}
                        {child.type === FieldTypes.DATE && (
                            <DateFieldSettings
                                field={child}
                                sources={getDateRuleSources(formFields || [], child.id)}
                                onChange={(patch) => patchProps(child, patch)}
                                sourceHint={`Rules can compare with an earlier date question of the same ${itemLabel.toLowerCase()}.`}
                            />
                        )}
                        {logic && (
                            <div className="flex flex-col gap-1.5">
                                {logic.conditions.map((condition, conditionIndex) => (
                                    <ConditionRow
                                        key={conditionIndex}
                                        condition={condition}
                                        sources={sources}
                                        onChange={(patch) => patchProps(child, { logic: { ...logic, conditions: logic.conditions.map((c, i) => (i === conditionIndex ? { ...c, ...patch } : c)) } })}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                );
            })}
            <label className="text-black-700 flex w-fit items-center gap-2 text-sm">
                <Plus className="h-4 w-4" aria-hidden="true" />
                <select
                    aria-label="Add a question to the group"
                    className={`${inputClass} w-56`}
                    value=""
                    onChange={(e) => {
                        if (!e.target.value) return;
                        commit([...children, { ...newGroupChild(e.target.value, children.length), title: '' }]);
                    }}
                >
                    <option value="">Add a question to the group…</option>
                    {CHILD_TYPES.map((option) => (
                        <option key={option.type} value={option.type}>
                            {option.name}
                        </option>
                    ))}
                </select>
            </label>
            <div className="text-black-500 flex items-center gap-2 text-xs" aria-hidden="true">
                <span className="rounded-md border border-dashed px-2 py-1">+ Add another {itemLabel}</span>
                respondents see this below each group of answers
            </div>
        </div>
    );
}
