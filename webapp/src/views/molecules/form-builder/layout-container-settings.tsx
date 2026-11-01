'use client';

import { useState } from 'react';

import { useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';

import { useLayoutContainerActions } from '@app/lib/hooks/use-layout-containers';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { FieldConditionalLogic, LogicCondition, LogicalOperator } from '@app/models/types/form-builder-shared';
import { Switch } from '@app/shadcn/components/ui/switch';
import { activeContainerAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderFieldsValue, usePageShell } from '@app/store/jotai/entity-hooks';
import { membersOf, pageFieldsOf } from '@app/utils/layout-containers';
import { ConditionRow, buildSourceFields, isConditionComplete, isConditionSource, newConditionFor, sameSourceFields, selectClass } from '@app/views/molecules/form-builder/condition-editor-shared';
import { InspectorSection } from '@app/views/molecules/form-builder/inspector-controls';

/**
 * The inspector for a selected layout container: whether the whole panel,
 * field set or tabs strip shows or hides by earlier answers. Its title, tabs
 * and questions are edited on the canvas frame itself. The rule reads only
 * questions before the container (the server refuses others), so the choice
 * of sources is the questions of earlier pages and the page's own questions
 * above its first one.
 */
export default function LayoutContainerSettings() {
    const { t } = useTranslation('builder');
    const selected = useAtomValue(activeContainerAtom);
    const page = usePageShell(selected?.pageId);
    const actions = useLayoutContainerActions();
    const { layoutContainersEnabled } = useWorkspacePermissions();
    const container = page?.properties?.containers?.find((c) => c.id === selected?.id);
    const pageIndex = page?.index;
    const firstId = container ? membersOf(container)[0] : undefined;
    // questions before the container: on earlier pages, or above its first question on this page
    const sources = useBuilderFieldsValue(
        (formFields) => {
            if (pageIndex === undefined || !firstId) return [];
            const own = formFields?.[pageIndex];
            const firstAt = pageFieldsOf(own).findIndex((field) => field.id === firstId);
            return buildSourceFields(formFields || [], (_slide, sIdx, field) => isConditionSource(field) && (sIdx < pageIndex || (sIdx === pageIndex && pageFieldsOf(own).findIndex((f) => f.id === field.id) < firstAt)));
        },
        [pageIndex, firstId],
        sameSourceFields
    );
    // The rule is edited here and saved once every condition is complete: the engine takes no half-written condition.
    const stored = container?.logic as FieldConditionalLogic | undefined;
    const [draft, setDraft] = useState<FieldConditionalLogic | undefined>(stored);
    const storedKey = JSON.stringify(stored ?? null);
    const [seen, setSeen] = useState(`${container?.id}:${storedKey}`);
    if (seen !== `${container?.id}:${storedKey}`) {
        setSeen(`${container?.id}:${storedKey}`);
        setDraft(stored);
    }
    if (!page || !container) return null;
    const kind = t(container.type === 'tabs' ? 'LAYOUT.TABS' : container.type === 'fieldset' ? 'LAYOUT.FIELDSET' : 'LAYOUT.PANEL').toLowerCase();
    const logic = draft;
    const editable = layoutContainersEnabled;
    const complete = !logic || logic.conditions.every(isConditionComplete);
    const commit = (next: FieldConditionalLogic | undefined) => {
        setDraft(next);
        if (!next || next.conditions.every(isConditionComplete)) actions.update(page.id, container.id, (c) => ({ ...c, logic: next }), 'Edit container visibility', `container-logic-${container.id}`);
    };
    const patchCondition = (index: number, patch: Partial<LogicCondition>) => logic && commit({ ...logic, conditions: logic.conditions.map((c, i) => (i === index ? { ...c, ...patch } : c)) });

    return (
        <div className="flex flex-col" data-layout-container-settings={container.id}>
            <InspectorSection title={t('LAYOUT.SECTION')}>
                <p className="text-xs leading-relaxed text-black-600">{t('LAYOUT.NOTE')}</p>
                {!layoutContainersEnabled && <p className="text-xs leading-relaxed text-black-700">{t('LAYOUT.OFF')}</p>}
            </InspectorSection>
            <InspectorSection title={t('LAYOUT.VISIBILITY')}>
                {sources.length === 0 && !logic ? (
                    <p className="text-xs text-black-600">{t('LAYOUT.VISIBILITY_NONE', { kind })}</p>
                ) : (
                    <div className="flex flex-col gap-3">
                        <div className="flex w-full items-center justify-between gap-2">
                            <span className="text-[11px] text-black-600">{t('LAYOUT.VISIBILITY_NOTE', { kind })}</span>
                            <Switch
                                aria-label={t('LAYOUT.VISIBILITY_NOTE', { kind })}
                                checked={!!logic}
                                disabled={!editable}
                                onCheckedChange={(on) => commit(on ? { action: 'SHOW', operator: LogicalOperator.AND, conditions: [newConditionFor(sources)] } : undefined)}
                            />
                        </div>
                        {logic && (
                            <div className="flex flex-col gap-3">
                                <div className="flex flex-col gap-1.5 text-xs text-black-600">
                                    <select className={selectClass} value={logic.action} disabled={!editable} onChange={(event) => commit({ ...logic, action: event.target.value as any })}>
                                        <option value="SHOW">{t('LAYOUT.SHOW_WHEN', { kind })}</option>
                                        <option value="HIDE">{t('LAYOUT.HIDE_WHEN', { kind })}</option>
                                    </select>
                                    {logic.conditions.length > 1 && (
                                        <div className="flex items-center gap-1">
                                            <span className="shrink-0">Match</span>
                                            <select className={selectClass} value={logic.operator} disabled={!editable} onChange={(event) => commit({ ...logic, operator: event.target.value as LogicalOperator })}>
                                                <option value={LogicalOperator.AND}>all</option>
                                                <option value={LogicalOperator.OR}>any</option>
                                            </select>
                                            <span className="shrink-0">of these:</span>
                                        </div>
                                    )}
                                </div>
                                {logic.conditions.map((condition, index) => (
                                    <ConditionRow
                                        key={index}
                                        condition={condition}
                                        sources={sources}
                                        onChange={(patch) => patchCondition(index, patch)}
                                        onRemove={editable && logic.conditions.length > 1 ? () => commit({ ...logic, conditions: logic.conditions.filter((_, i) => i !== index) }) : undefined}
                                    />
                                ))}
                                {!complete && <p className="text-[11px] text-black-600">{t('LAYOUT.COMPLETE_RULE')}</p>}
                                {editable && (
                                    <button type="button" className="w-fit text-xs font-medium text-brand-500 hover:text-brand-600" onClick={() => commit({ ...logic, conditions: [...logic.conditions, newConditionFor(sources)] })}>
                                        + Add condition
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </InspectorSection>
        </div>
    );
}
