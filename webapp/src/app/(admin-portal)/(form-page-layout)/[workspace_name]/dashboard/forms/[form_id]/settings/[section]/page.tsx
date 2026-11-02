'use client';

import { useEffect } from 'react';

import { useParams, useRouter } from 'next/navigation';

import FormSettingsPage from '@Components/form/settings';
import { isSettingsPageKey, settingsPages } from '@Components/form/settings-pages';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';

/**
 * One page of the form's Settings. A page this form has nothing to show on (Availability and Automations for a form
 * imported from elsewhere, an unknown name) sends the visitor to Access instead of showing an empty page.
 */
export default function Page() {
    const params = useParams<{ workspace_name: string; form_id: string; section: string }>();
    const router = useRouter();
    const form = useAppSelector(selectForm);
    const { can, isLoading } = useWorkspacePermissions();
    const section = params?.section;
    const available = isSettingsPageKey(section) && settingsPages(form, can).includes(section);
    // Without form.edit the page says so itself (and the redirect would only land on the same message).
    const redirectToAccess = !isLoading && !!form?.formId && can(WorkspacePermission.FORM_EDIT) && !available;

    useEffect(() => {
        if (redirectToAccess) router.replace(`/${params.workspace_name}/dashboard/forms/${params.form_id}/settings/access`);
    }, [redirectToAccess, router, params.workspace_name, params.form_id]);

    if (!isSettingsPageKey(section) || redirectToAccess) return null;
    return <FormSettingsPage page={section} />;
}
