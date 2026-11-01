'use client';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';

import OptionListsClient from './_components/option-lists-client';

/**
 * Workspace lists: reference data (municipalities, products, branches) that choice questions take their options
 * from. Everyone who reads forms sees the lists; changing them needs form.edit (the API refuses the rest, the page
 * only hides what would be refused). The sidebar item shows only while this server takes options from lists.
 */
export default function ListsPage() {
    const { t } = useTranslation('builder');
    const { ready, optionSourcesEnabled } = useWorkspacePermissions();
    if (!ready) return <div className="pb-10 text-sm text-black-600">{t('LISTS.LOADING')}</div>;
    if (!optionSourcesEnabled) return <p className="pb-10 text-sm text-black-700">{t('LISTS.TURNED_OFF')}</p>;
    return <OptionListsClient />;
}
