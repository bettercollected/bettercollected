'use client';

import { useTranslation } from 'react-i18next';

import { ContainerKind, useLayoutContainerActions } from '@app/lib/hooks/use-layout-containers';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { usePageFieldIds, usePageShell } from '@app/store/jotai/entity-hooks';
import { containerOfField, tabOfField } from '@app/utils/layout-containers';
import { InspectorSection } from '@app/views/molecules/form-builder/inspector-controls';

const button =
    'border-control hover:bg-black-100 focus-visible:ring-brand-500 w-full rounded-md border bg-white px-3 py-1.5 text-left text-xs font-medium text-black-800 focus-visible:ring-2 focus-visible:outline-hidden disabled:cursor-not-allowed disabled:opacity-40';

/**
 * The question's Layout section: put it in a new panel, field set or tabs
 * strip, or say which one it is in and take it out. Shown while the server
 * allows containers (LAYOUT_CONTAINERS_ENABLED), or when the question is in
 * one (then it can be taken out). Not for internal questions (staff only:
 * they are never shown to respondents) and not for a repeating group's
 * questions (a container holds the page's questions).
 */
export default function FieldLayoutSection({ field, pageId }: { field: StandardFormFieldDto; pageId: string }) {
    const { t } = useTranslation('builder');
    const actions = useLayoutContainerActions();
    const { layoutContainersEnabled } = useWorkspacePermissions();
    const page = usePageShell(pageId);
    // a page's own question (not a repeating group's)
    const onPage = usePageFieldIds(pageId).includes(field.id);
    const container = containerOfField(page, field.id);
    if (!onPage || field.internal || field.type === FieldTypes.SLIDE) return null;
    if (!layoutContainersEnabled && !container) return null;
    const names = { title: t('LAYOUT.DEFAULT_PANEL'), tab: (n: number) => t('LAYOUT.DEFAULT_TAB', { n }) };
    const group = (kind: ContainerKind) => actions.group(pageId, kind, [field.id], { ...names, title: kind === 'fieldset' ? t('LAYOUT.DEFAULT_FIELDSET') : names.title });
    const kindName = container ? t(container.type === 'tabs' ? 'LAYOUT.TABS' : container.type === 'fieldset' ? 'LAYOUT.FIELDSET' : 'LAYOUT.PANEL').toLowerCase() : '';
    const tabTitle = container?.type === 'tabs' ? container.tabs?.find((tab) => tab.id === tabOfField(container, field.id))?.title : undefined;
    return (
        <InspectorSection title={t('LAYOUT.SECTION')}>
            {container ? (
                <div className="flex flex-col gap-2">
                    <p className="text-xs leading-relaxed text-black-700">{container.type === 'tabs' ? t('LAYOUT.IN_TABS', { title: tabTitle ?? '' }) : t('LAYOUT.IN_CONTAINER', { kind: kindName, title: container.title ?? '' })}</p>
                    <button type="button" className={button} onClick={() => actions.moveOut(pageId, field.id)}>
                        {t('LAYOUT.MOVE_OUT')}
                    </button>
                </div>
            ) : (
                <div className="flex flex-col gap-2">
                    <p className="text-xs leading-relaxed text-black-600">{t('LAYOUT.NOT_GROUPED')}</p>
                    <button type="button" className={button} onClick={() => group('panel')}>
                        {t('LAYOUT.GROUP_PANEL')}
                    </button>
                    <button type="button" className={button} onClick={() => group('fieldset')}>
                        {t('LAYOUT.GROUP_FIELDSET')}
                    </button>
                    <button type="button" className={button} onClick={() => group('tabs')}>
                        {t('LAYOUT.GROUP_TABS')}
                    </button>
                </div>
            )}
        </InspectorSection>
    );
}
