'use client';

import { useState } from 'react';

import { useStore } from 'jotai';
import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { FieldRule } from '@app/lib/field-rules';
import { canCarryRules } from '@app/lib/form-ops/field-rule-checks';
import type { FieldRuleSpec } from '@app/lib/form-ops/types';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { dispatchAtom } from '@app/store/jotai/form-document';
import FieldRulesSettings from '@app/views/molecules/form-builder/field-rules-settings';
import { InspectorSection } from '@app/views/molecules/form-builder/inspector-controls';

/**
 * The question's Rules section: shown when the server allows rules (the
 * FIELD_RULES_ENABLED switch), or when the question already has some (then
 * they are listed, not editable). Edits go through `set_field_rules`, so the
 * ops engine refuses what a save would refuse and each edit is an undo step.
 *
 * Until it has rules or "Add a rule" is chosen, only a button is shown: the
 * editor reads the whole form (its sources and checks), and the inspector
 * must not re-render for every key typed in another question.
 */
export default function FieldRulesSection({ field }: { field: StandardFormFieldDto }) {
    const { t } = useTranslation('builder');
    // The server says whether it takes rules (with the permissions): one switch, the backend's.
    const { fieldRulesEnabled: enabled } = useWorkspacePermissions();
    const has = Array.isArray(field.properties?.rules) && field.properties.rules.length > 0;
    // the question the editor was opened for (selecting another one closes it)
    const [opened, setOpened] = useState<string | null>(null);
    if (!canCarryRules(field) || (!enabled && !has)) return null;
    const open = has || opened === field.id;
    return (
        <InspectorSection title={t('FIELD_RULES.TITLE')}>
            {open ? (
                <RulesEditor field={field} editable={enabled} addFirst={!has && opened === field.id} />
            ) : (
                <div className="flex w-full flex-col gap-2">
                    <p className="text-[11px] leading-relaxed text-black-600">{t('FIELD_RULES.EMPTY')}</p>
                    <button
                        type="button"
                        data-field-rules-add=""
                        onClick={() => setOpened(field.id)}
                        className="inline-flex w-fit items-center gap-1 rounded text-xs font-medium text-brand-500 hover:text-brand-600 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                    >
                        <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                        {t('FIELD_RULES.ADD')}
                    </button>
                </div>
            )}
        </InspectorSection>
    );
}

function RulesEditor({ field, editable, addFirst }: { field: StandardFormFieldDto; editable: boolean; addFirst: boolean }) {
    const store = useStore();
    const { formFields } = useFormFieldsAtom();
    const { formState } = useFormState();
    const commit = (rules: FieldRule[] | undefined, coalesceKey?: string) =>
        store.set(dispatchAtom, { ops: [{ op: 'set_field_rules', fieldId: field.id, rules: (rules as unknown as FieldRuleSpec[] | undefined) ?? null }], label: 'Edit rules', coalesceKey });
    return <FieldRulesSettings key={field.id} field={field} slides={formFields || []} hiddenNames={formState.hiddenFields ?? []} editable={editable} addFirst={addFirst} onChange={commit} />;
}
