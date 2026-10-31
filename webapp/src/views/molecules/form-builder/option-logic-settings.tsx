'use client';

import { useId } from 'react';

import { useAtomValue } from 'jotai';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldConditionalLogic, LogicCondition, LogicalOperator } from '@app/models/types/form-builder-shared';
import { Switch } from '@app/shadcn/components/ui/switch';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderFieldsValue, useField, useFieldActions, usePageShell } from '@app/store/jotai/entity-hooks';
import { OPTION_CONDITIONS_MAX, OPTION_LOGIC_OPTIONS_MAX, OptionFilter, OptionLogicWarning, optionLogicWarnings } from '@app/utils/option-logic-checks';

import { ConditionRow, SourceField, buildSourceFields, isConditionSource, newConditionFor, sameSourceFields, selectClass } from './condition-editor-shared';

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** The text of an option as the builder names it (its text, else "Item n"). */
export const optionLabel = (choice: { value?: string; label?: string } | undefined, index: number, t: Translate): string => choice?.value?.trim() || choice?.label?.trim() || t('OPTION_LOGIC.UNNAMED', { n: index + 1 });

const questionText = (field: StandardFormFieldDto | undefined, t: Translate): string => {
    const title = typeof field?.title === 'string' ? field.title : '';
    return title.trim() || t('OPTION_LOGIC.UNTITLED');
};

const isChoiceQuestion = (field: StandardFormFieldDto | undefined) => field?.type === FieldTypes.MULTIPLE_CHOICE || field?.type === FieldTypes.DROP_DOWN;

/**
 * A choice question's option logic in the inspector: per option "Show this
 * option when…" with the same condition builder as a question's logic, and
 * "Filter options by an earlier answer", a table of the question's options by
 * the options of an earlier choice question. What the server would warn about
 * is shown under them (`optionLogicWarnings`, shared with the server's check).
 * Only for a choice question of a page: a repeating group's question has none.
 */
export default function OptionLogicSettings() {
    const { t } = useBuilderTranslation();
    const activeFieldComponent = useAtomValue(activeFieldAtom);
    const activeSlideComponent = useAtomValue(activeSlideAtom);
    const field = useField(activeFieldComponent?.id);
    const slide = usePageShell(activeSlideComponent?.id);
    const { updateChoiceLogic, updateOptionFilter } = useFieldActions();
    const slideIndex = slide?.index;
    const fieldIndex = field?.index;
    const fieldId = field?.id;

    // Earlier questions of the page level (an option reads the answers given before it).
    const earlier = (formSlideIndex: number, candidate: StandardFormFieldDto) =>
        slideIndex !== undefined && fieldIndex !== undefined && (formSlideIndex < slideIndex || (formSlideIndex === slideIndex && candidate.index < fieldIndex)) && candidate.id !== fieldId;
    const sources = useBuilderFieldsValue(
        (formFields) => (slideIndex === undefined || fieldIndex === undefined ? [] : buildSourceFields(formFields || [], (_slide, sIdx, candidate) => earlier(sIdx, candidate) && isConditionSource(candidate))),
        [slideIndex, fieldIndex, fieldId],
        sameSourceFields
    );
    const choiceSources = useBuilderFieldsValue(
        (formFields) => (slideIndex === undefined || fieldIndex === undefined ? [] : buildSourceFields(formFields || [], (_slide, sIdx, candidate) => earlier(sIdx, candidate) && isChoiceQuestion(candidate))),
        [slideIndex, fieldIndex, fieldId],
        sameSourceFields
    );
    const onPageLevel = useBuilderFieldsValue((formFields) => !!fieldId && slideIndex !== undefined && !!formFields?.[slideIndex]?.properties?.fields?.some((candidate) => candidate.id === fieldId), [fieldId, slideIndex]);
    const warnings = useBuilderFieldsValue(
        (formFields) => (fieldId ? optionLogicWarnings(formFields || []).filter((warning) => warning.fieldId === fieldId) : []),
        [fieldId],
        (a, b) => JSON.stringify(a) === JSON.stringify(b)
    );

    // The server says whether it takes choice logic (with the permissions): one switch, the backend's.
    const { choiceLogicEnabled: editable } = useWorkspacePermissions();

    if (!field || !slide || !isChoiceQuestion(field) || field.internal || !onPageLevel) return null;
    const choices = (field.properties?.choices ?? []).filter((choice) => !!choice.id);
    // Switched off: nothing to create, and what the question has is shown read-only (it is still applied to responses).
    if (!editable && !field.properties?.optionFilter && !choices.some((choice) => !!choice.logic)) return null;

    return (
        <div className="flex flex-col gap-4 border-t border-black-300 pt-4" data-testid="option-logic-settings">
            <div>
                <div className="text-xs font-medium text-black-700">{t('OPTION_LOGIC.TITLE')}</div>
                <div className="text-[11px] text-black-600">{t('OPTION_LOGIC.HINT')}</div>
            </div>
            {!editable && (
                <p className="text-[11px] leading-relaxed text-black-600" data-testid="option-logic-disabled">
                    {t('OPTION_LOGIC.DISABLED_NOTE')}
                </p>
            )}
            <fieldset disabled={!editable} className="m-0 flex min-w-0 flex-col gap-4 border-0 p-0">
                {sources.length === 0 ? (
                    <p className="text-xs text-black-600">{t('OPTION_LOGIC.NO_SOURCES')}</p>
                ) : (
                    <ul className="flex flex-col gap-3">
                        {choices.map((choice, index) => (
                            <li key={choice.id}>
                                <OptionLogicRow label={optionLabel(choice, index, t)} logic={choice.logic} sources={sources} t={t} onChange={(next) => updateChoiceLogic(field.id, choice.id, next)} />
                            </li>
                        ))}
                    </ul>
                )}

                <OptionFilterEditor field={field} choices={choices} sources={choiceSources} t={t} onChange={(filter) => updateOptionFilter(field.id, filter)} />

                {warnings.length > 0 && <Warnings field={field} warnings={warnings} sources={choiceSources} t={t} />}
            </fieldset>
        </div>
    );
}

/** One option: its switch and, when on, "Show/Hide this option when…" with the condition rows. */
function OptionLogicRow({ label, logic, sources, onChange, t }: { label: string; logic: FieldConditionalLogic | undefined; sources: SourceField[]; onChange: (logic: FieldConditionalLogic | undefined) => void; t: Translate }) {
    const labelId = useId();
    const enabled = !!logic;
    const patchCondition = (idx: number, patch: Partial<LogicCondition>) => logic && onChange({ ...logic, conditions: logic.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)) });
    return (
        <div className="flex flex-col gap-2 rounded-md border border-black-300 p-2" role="group" aria-labelledby={labelId}>
            <div className="flex w-full items-center justify-between gap-3">
                <span id={labelId} className="min-w-0 truncate text-xs font-medium text-black-800">
                    {label}
                </span>
                <Switch aria-label={t('OPTION_LOGIC.SWITCH', { option: label })} checked={enabled} onCheckedChange={(on) => onChange(on ? { action: 'SHOW', operator: LogicalOperator.AND, conditions: [newConditionFor(sources)] } : undefined)} />
            </div>
            {enabled && logic && (
                <div className="flex flex-col gap-2">
                    <div className="flex flex-col gap-1.5 text-xs text-black-600">
                        <select aria-label={label} className={selectClass} value={logic.action} onChange={(e) => onChange({ ...logic, action: e.target.value as FieldConditionalLogic['action'] })}>
                            <option value="SHOW">{t('OPTION_LOGIC.SHOW_WHEN')}</option>
                            <option value="HIDE">{t('OPTION_LOGIC.HIDE_WHEN')}</option>
                        </select>
                        {logic.conditions.length > 1 && (
                            <div className="flex items-center gap-1">
                                <span className="shrink-0">{t('OPTION_LOGIC.MATCH')}</span>
                                <select aria-label={t('OPTION_LOGIC.MATCH')} className={selectClass} value={logic.operator} onChange={(e) => onChange({ ...logic, operator: e.target.value as LogicalOperator })}>
                                    <option value={LogicalOperator.AND}>{t('OPTION_LOGIC.ALL')}</option>
                                    <option value={LogicalOperator.OR}>{t('OPTION_LOGIC.ANY')}</option>
                                </select>
                                <span className="shrink-0">{t('OPTION_LOGIC.OF_THESE')}</span>
                            </div>
                        )}
                    </div>
                    {logic.conditions.map((condition, idx) => (
                        <ConditionRow
                            key={idx}
                            condition={condition}
                            sources={sources}
                            onChange={(patch) => patchCondition(idx, patch)}
                            onRemove={logic.conditions.length > 1 ? () => onChange({ ...logic, conditions: logic.conditions.filter((_, i) => i !== idx) }) : undefined}
                        />
                    ))}
                    {logic.conditions.length < OPTION_CONDITIONS_MAX && (
                        <button type="button" className="w-fit text-xs font-medium text-brand-500 hover:text-brand-600" onClick={() => onChange({ ...logic, conditions: [...logic.conditions, newConditionFor(sources)] })}>
                            {t('OPTION_LOGIC.ADD_CONDITION')}
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

/**
 * "Filter options by an earlier answer": the earlier choice question, and a
 * table (a row per option of this question, a column per option of the earlier
 * one) of checkboxes: tick the options offered for each answer. A real table,
 * so a screen reader reads each box with its row and its column.
 */
function OptionFilterEditor({
    field,
    choices,
    sources,
    onChange,
    t
}: {
    field: StandardFormFieldDto;
    choices: Array<{ id: string; value?: string; label?: string }>;
    sources: SourceField[];
    onChange: (filter: OptionFilter | undefined) => void;
    t: Translate;
}) {
    const switchId = useId();
    const selectId = useId();
    const filter = field.properties?.optionFilter;
    const enabled = !!filter;
    const source = sources.find((candidate) => candidate.field.id === filter?.fieldId)?.field;
    const sourceChoices = (source?.properties?.choices ?? []).filter((choice) => !!choice.id);
    const shown = (when: string, option: string) => !!filter?.mapping.find((entry) => entry.when === when)?.show.includes(option);

    const toggleFilter = (on: boolean) => {
        if (!on) return onChange(undefined);
        const first = sources[0]?.field;
        // every option offered for every answer to start with: nothing is lost until the creator unticks it
        onChange({ fieldId: first?.id ?? '', mapping: (first?.properties?.choices ?? []).filter((choice) => choice.id).map((choice) => ({ when: choice.id, show: choices.map((own) => own.id) })) });
    };
    const chooseSource = (id: string) => {
        const next = sources.find((candidate) => candidate.field.id === id)?.field;
        onChange({ fieldId: id, mapping: (next?.properties?.choices ?? []).filter((choice) => choice.id).map((choice) => ({ when: choice.id, show: choices.map((own) => own.id) })) });
    };
    const toggleCell = (when: string, option: string, on: boolean) => {
        if (!filter) return;
        const mapping = filter.mapping.some((entry) => entry.when === when) ? filter.mapping : [...filter.mapping, { when, show: [] }];
        onChange({ ...filter, mapping: mapping.map((entry) => (entry.when === when ? { ...entry, show: on ? [...entry.show.filter((id) => id !== option), option] : entry.show.filter((id) => id !== option) } : entry)) });
    };

    return (
        <div className="flex flex-col gap-3">
            <div className="flex w-full items-center justify-between gap-4">
                <label htmlFor={switchId} className="text-xs text-black-700">
                    {t('OPTION_LOGIC.FILTER_TITLE')}
                </label>
                <Switch id={switchId} checked={enabled} disabled={sources.length === 0 && !enabled} onCheckedChange={toggleFilter} aria-describedby={`${switchId}-hint`} />
            </div>
            <p id={`${switchId}-hint`} className="text-[11px] leading-relaxed text-black-600">
                {sources.length === 0 && !enabled ? t('OPTION_LOGIC.FILTER_NO_SOURCES') : t('OPTION_LOGIC.FILTER_HINT')}
            </p>
            {enabled && filter && (
                <div className="flex flex-col gap-2">
                    <label htmlFor={selectId} className="text-xs text-black-700">
                        {t('OPTION_LOGIC.FILTER_SOURCE')}
                    </label>
                    <select id={selectId} className={selectClass} value={filter.fieldId} onChange={(e) => chooseSource(e.target.value)}>
                        {!source && <option value={filter.fieldId}>{filter.fieldId}</option>}
                        {sources.map((candidate) => (
                            <option key={candidate.field.id} value={candidate.field.id}>
                                {candidate.label}
                            </option>
                        ))}
                    </select>
                    {source && (
                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse text-xs" data-testid="option-filter-table">
                                <caption className="sr-only">{t('OPTION_LOGIC.FILTER_TABLE', { question: questionText(field, t), source: questionText(source, t) })}</caption>
                                <thead>
                                    <tr>
                                        <th scope="col" className="p-1 text-left font-medium text-black-700">
                                            {t('OPTION_LOGIC.FILTER_OPTION')}
                                        </th>
                                        {sourceChoices.map((answer, index) => (
                                            <th key={answer.id} scope="col" className="max-w-[7rem] p-1 text-center font-medium text-black-700">
                                                <span className="block truncate" title={t('OPTION_LOGIC.FILTER_ANSWER', { answer: optionLabel(answer, index, t) })}>
                                                    {optionLabel(answer, index, t)}
                                                </span>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {choices.map((own, ownIndex) => (
                                        <tr key={own.id} className="border-t border-black-300">
                                            <th scope="row" className="max-w-[8rem] truncate p-1 text-left font-normal text-black-800">
                                                {optionLabel(own, ownIndex, t)}
                                            </th>
                                            {sourceChoices.map((answer, answerIndex) => (
                                                <td key={answer.id} className="p-1 text-center">
                                                    <input
                                                        type="checkbox"
                                                        className="h-4 w-4 accent-brand-500"
                                                        checked={shown(answer.id, own.id)}
                                                        aria-label={t('OPTION_LOGIC.FILTER_CELL', { option: optionLabel(own, ownIndex, t), source: questionText(source, t), answer: optionLabel(answer, answerIndex, t) })}
                                                        onChange={(e) => toggleCell(answer.id, own.id, e.target.checked)}
                                                    />
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/** What the shared check found: said in words, as a note (never blocking). */
function Warnings({ field, warnings, sources, t }: { field: StandardFormFieldDto; warnings: OptionLogicWarning[]; sources: SourceField[]; t: Translate }) {
    const source = sources.find((candidate) => candidate.field.id === field.properties?.optionFilter?.fieldId)?.field;
    const optionName = (owner: StandardFormFieldDto | undefined, id: string | undefined) => {
        const choices = owner?.properties?.choices ?? [];
        const index = choices.findIndex((choice) => choice.id === id);
        return optionLabel(choices[index], index < 0 ? 0 : index, t);
    };
    const lines = warnings.map((warning) => {
        switch (warning.code) {
            case 'unreachable_option':
                return t('OPTION_LOGIC.WARNING_UNREACHABLE', { option: optionName(field, warning.optionId), source: questionText(source, t) });
            case 'too_many_options':
                return t('OPTION_LOGIC.WARNING_TOO_MANY', { max: OPTION_LOGIC_OPTIONS_MAX });
            case 'source_option_unmapped':
                return t('OPTION_LOGIC.WARNING_UNMAPPED', { option: optionName(source, warning.optionId), source: questionText(source, t) });
            default:
                return t('OPTION_LOGIC.WARNING_EMPTY');
        }
    });
    return (
        <div role="note" aria-label={t('OPTION_LOGIC.WARNINGS')} className="rounded-md border border-amber-300 bg-amber-50 p-2 text-[11px] leading-relaxed text-amber-900" data-testid="option-logic-warnings">
            <ul className="flex list-disc flex-col gap-0.5 pl-4">
                {lines.map((line, index) => (
                    <li key={index}>{line}</li>
                ))}
            </ul>
        </div>
    );
}
