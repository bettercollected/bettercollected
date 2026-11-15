'use client';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';

import SectionsClient from './_components/sections-client';
import { PageSurface } from '@app/components/ui/page-surface';

/**
 * Reusable sections: groups of questions saved once (from the form builder's "Save as section") and copied into
 * forms. Everyone who reads forms sees the library; renaming and deleting need form.edit (the API refuses the
 * rest, the page only hides what would be refused). The sidebar item shows only while this server has the library.
 */
export default function SectionsPage() {
    const { t } = useTranslation('builder');
    const { ready, reusableSectionsEnabled } = useWorkspacePermissions();
    const content = !ready ? <p className="text-sm text-black-600">{t('SECTIONS_LIB.PAGE.LOADING')}</p> : !reusableSectionsEnabled ? <p className="text-sm text-black-700">{t('SECTIONS_LIB.PAGE.TURNED_OFF')}</p> : <SectionsClient />;
    return <PageSurface>{content}</PageSurface>;
}
