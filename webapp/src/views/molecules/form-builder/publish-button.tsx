import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { usePublishV2FormMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { usePathname, useRouter } from 'next/navigation';

const PublishButton = ({ refresh = false }: { refresh?: boolean }) => {
    const { toast } = useToast();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();
    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();
    const router = useRouter();
    const pathname = usePathname();
    const authState = useAppSelector(selectAuth);

    const publishForm = async () => {
        const response: any = await publishV2Form({
            workspaceId: workspace.id,
            formId: standardForm.formId
        });

        if (response.data) {
            if (refresh && pathname) {
                router.push(pathname);
                toast({ description: 'Form Published' });
                return;
            }
            openDialogModal('FORM_PUBLISHED');
        }
    };
    return (
        <Button isLoading={isLoading} onClick={publishForm} data-umami-event={'Publish Button'} data-umami-event-email={authState.email}>
            Publish
        </Button>
    );
};

export default PublishButton;
