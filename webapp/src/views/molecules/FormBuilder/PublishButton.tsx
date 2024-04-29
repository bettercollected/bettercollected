import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { usePublishV2FormMutation } from '@app/store/redux/formApi';
import { selectWorkspace } from '@app/store/workspaces/slice';

const PublishButton = () => {
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();
    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();

    const publishForm = async () => {
        const response: any = await publishV2Form({
            workspaceId: workspace.id,
            formId: standardForm.formId
        });
        if (response.data) {
            openDialogModal('FORM_PUBLISHED');
        }
    };
    return (
        <Button isLoading={isLoading} onClick={publishForm}>
            Publish
        </Button>
    );
};

export default PublishButton;
