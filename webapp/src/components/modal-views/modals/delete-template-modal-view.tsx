import React from 'react';

import { useRouter } from 'next/router';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';
import { toast } from 'react-toastify';

import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteTemplateMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function DeleteTemplateConfirmationModalView({ template }: { template: IFormTemplateDto }) {
    const [deleteTemplate] = useDeleteTemplateMutation();
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const handleDeleteTemplate = async () => {
        try {
            const response: any = await deleteTemplate({
                workspace_id: workspace?.id,
                template_id: template?.id
            });
            if (response?.data) {
                toast('Deleted Successfully', { type: 'success' });
                router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };
    return (
        <GenericHalfModal
            headerTitle="Delete Form Template"
            positiveAction={handleDeleteTemplate}
            positiveText="Delete"
            type="danger"
            title={'Are You Sure To Delete This Template?'}
            subTitle={'Once the creator deletes your response, it will be permanently removed.'}
        />
    );
}
