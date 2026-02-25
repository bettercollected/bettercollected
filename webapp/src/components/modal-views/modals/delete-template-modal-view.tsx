
import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import GenericHalfModal from '@Components/Common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteTemplateMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function DeleteTemplateConfirmationModalView({ template }: { template: IFormTemplateDto }) {
    const { toast } = useToast();
    const { t } = useTranslation();
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
                toast({ description: 'Deleted Successfully' });
                router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast({ description: 'Error Occurred', variant: 'destructive' });
            }
        } catch (err) {
            toast({ description: 'Error Occurred', variant: 'destructive' });
        }
    };
    return <GenericHalfModal headerTitle={t('TEMPLATE.DELETE_MODAL.HEADER')} positiveAction={handleDeleteTemplate} positiveText={t('BUTTON.DELETE')} type="danger" title={t('TEMPLATE.DELETE_MODAL.TITLE')} subTitle={t('TEMPLATE.DELETE_MODAL.SUBTITLE')} />;
}