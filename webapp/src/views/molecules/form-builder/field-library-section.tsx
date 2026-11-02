'use client';

import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { useSectionActions } from '@app/lib/hooks/use-reusable-sections';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useAppSelector } from '@app/store/hooks';
import { usePageFieldIds, usePageShell } from '@app/store/jotai/entity-hooks';
import { useGetSectionsQuery } from '@app/store/reusable-sections/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { containerOfField, membersOf } from '@app/utils/layout-containers';
import { libraryOf } from '@app/utils/reusable-sections';
import { InspectorSection } from '@app/views/molecules/form-builder/inspector-controls';
import SaveSectionDialog from '@app/views/molecules/form-builder/save-section-dialog';
import UpdateFromLibraryDialog from '@app/views/molecules/form-builder/update-from-library-dialog';

const button =
    'border-control hover:bg-black-100 focus-visible:ring-brand-500 w-full rounded-md border bg-white px-3 py-1.5 text-left text-xs font-medium text-black-800 focus-visible:ring-2 focus-visible:outline-hidden disabled:cursor-not-allowed disabled:opacity-40';

/**
 * The inspector's Library section (reusable sections, `REUSABLE_SECTIONS_ENABLED`): save this question, or the
 * panel, field set or tabs it is in, as a section of the workspace's library; and, for a question that was
 * copied from the library, say which section and version, update the copy from the library (with a diff) or save
 * the copy as the section's next version. Only for whoever may edit forms; only for a page's own questions
 * (a repeating group's question is saved with its group), and not for staff-only (internal) ones.
 */
export default function FieldLibrarySection({ field, pageId }: { field: StandardFormFieldDto; pageId: string }) {
    const { reusableSectionsEnabled, can } = useWorkspacePermissions();
    // the library's own hooks (the workspace, the sections, the builder's document) only run while it is there to use
    if (!reusableSectionsEnabled || !can(WorkspacePermission.FORM_EDIT)) return null;
    return <FieldLibraryBody field={field} pageId={pageId} />;
}

function FieldLibraryBody({ field, pageId }: { field: StandardFormFieldDto; pageId: string }) {
    const { t } = useTranslation('builder');
    const workspace = useAppSelector(selectWorkspace);
    const actions = useSectionActions();
    const page = usePageShell(pageId);
    const onPage = usePageFieldIds(pageId).includes(field.id);
    const origin = libraryOf(field);
    const { data: sections } = useGetSectionsQuery({ workspaceId: workspace?.id as string }, { skip: !workspace?.id || !origin });
    const [saving, setSaving] = useState<'question' | 'container' | null>(null);
    const [updating, setUpdating] = useState(false);
    const [savingCopy, setSavingCopy] = useState(false);
    if (!onPage || field.internal || field.type === FieldTypes.SLIDE) return null;
    const container = containerOfField(page, field.id);
    const kind = container ? t(container.type === 'tabs' ? 'LAYOUT.TABS' : container.type === 'fieldset' ? 'LAYOUT.FIELDSET' : 'LAYOUT.PANEL').toLowerCase() : '';
    const section = origin ? sections?.find((s) => s.id === origin.sectionId) : undefined;
    const saveQuestions = (name: string, description: string) =>
        saving === 'container' && container ? actions.saveAsSection({ pageId, fieldIds: membersOf(container), containerId: container.id, name, description }) : actions.saveAsSection({ pageId, fieldIds: [field.id], name, description });

    return (
        <InspectorSection title={t('SECTIONS_LIB.SECTION')}>
            <div className="flex flex-col gap-2">
                {origin && <p className="text-xs leading-relaxed text-black-700">{section ? t('SECTIONS_LIB.COPY_OF', { name: section.name, version: origin.version }) : sections ? t('SECTIONS_LIB.COPY_OF_GONE') : t('SECTIONS_LIB.COPY_OF_LOADING')}</p>}
                {origin && section && (
                    <>
                        <button type="button" className={button} onClick={() => setUpdating(true)}>
                            {t('SECTIONS_LIB.UPDATE.BUTTON')}
                        </button>
                        <button
                            type="button"
                            className={button}
                            disabled={savingCopy}
                            onClick={async () => {
                                setSavingCopy(true);
                                await actions.saveCopy(pageId, origin.instance);
                                setSavingCopy(false);
                            }}
                        >
                            {t('SECTIONS_LIB.SAVE_COPY')}
                        </button>
                    </>
                )}
                <button type="button" className={button} onClick={() => setSaving('question')}>
                    {t('SECTIONS_LIB.SAVE_QUESTION')}
                </button>
                {container && (
                    <button type="button" className={button} onClick={() => setSaving('container')}>
                        {t('SECTIONS_LIB.SAVE_CONTAINER', { kind })}
                    </button>
                )}
            </div>
            <SaveSectionDialog
                key={saving ?? 'none'}
                open={saving !== null}
                onOpenChange={(open) => !open && setSaving(null)}
                subject={saving === 'container' ? t('SECTIONS_LIB.SUBJECT_CONTAINER', { kind }) : t('SECTIONS_LIB.SUBJECT_QUESTION')}
                save={saveQuestions}
            />
            {origin && <UpdateFromLibraryDialog open={updating} onOpenChange={setUpdating} plan={() => actions.planUpdate(pageId, origin.instance)} apply={(plan) => actions.applyUpdate(pageId, plan)} />}
        </InspectorSection>
    );
}

/**
 * The same for a layout container selected on the canvas: save it, with its questions, as a section of the
 * library. A container that holds only the questions of a copy also offers the copy's update.
 */
export function ContainerLibrarySection({ pageId, containerId }: { pageId: string; containerId: string }) {
    const { reusableSectionsEnabled, can } = useWorkspacePermissions();
    if (!reusableSectionsEnabled || !can(WorkspacePermission.FORM_EDIT)) return null;
    return <ContainerLibraryBody pageId={pageId} containerId={containerId} />;
}

function ContainerLibraryBody({ pageId, containerId }: { pageId: string; containerId: string }) {
    const { t } = useTranslation('builder');
    const actions = useSectionActions();
    const page = usePageShell(pageId);
    const [saving, setSaving] = useState(false);
    const container = page?.properties?.containers?.find((c) => c.id === containerId);
    if (!container) return null;
    const kind = t(container.type === 'tabs' ? 'LAYOUT.TABS' : container.type === 'fieldset' ? 'LAYOUT.FIELDSET' : 'LAYOUT.PANEL').toLowerCase();
    return (
        <InspectorSection title={t('SECTIONS_LIB.SECTION')}>
            <button type="button" className={button} onClick={() => setSaving(true)}>
                {t('SECTIONS_LIB.SAVE_CONTAINER', { kind })}
            </button>
            <SaveSectionDialog
                key={saving ? 'open' : 'closed'}
                open={saving}
                onOpenChange={setSaving}
                defaultName={container.title ?? undefined}
                subject={t('SECTIONS_LIB.SUBJECT_CONTAINER', { kind })}
                save={(name, description) => actions.saveAsSection({ pageId, fieldIds: membersOf(container), containerId: container.id, name, description })}
            />
        </InspectorSection>
    );
}
