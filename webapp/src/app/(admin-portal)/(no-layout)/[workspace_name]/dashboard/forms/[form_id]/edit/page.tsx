'use client';

import { useEffect } from 'react';

import { useParams, useRouter } from 'next/navigation';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import FullScreenLoader from '@Components/ui/fullscreen-loader';
import FormEditPage from './_components/form-edit-page';

export default function FormPage(props: { params: Promise<{ form_id: string }> }) {

    const standardForm: any = useAppSelector(selectForm);
    const { can, isLoading } = useWorkspacePermissions();
    const canEdit = can(WorkspacePermission.FORM_EDIT);
    const router = useRouter();
    const routeParams = useParams<{ workspace_name: string; form_id: string }>();

    // Reviewers, Viewers and Privacy officers read the form, they don't edit
    // it (the backend refuses every save): send them to the preview.
    useEffect(() => {
        if (!isLoading && !canEdit && routeParams?.workspace_name && routeParams?.form_id) {
            router.replace(`/${routeParams.workspace_name}/dashboard/forms/${routeParams.form_id}/preview`);
        }
    }, [isLoading, canEdit, router, routeParams?.workspace_name, routeParams?.form_id]);

    if (!standardForm.formId || !canEdit) {
        return <FullScreenLoader />
    }

    return (
        <FormEditPage params={props.params} />
    );
}
