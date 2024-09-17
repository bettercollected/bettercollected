import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useAuthAtom } from '@app/store/jotai/auth';
import { usePublishV2FormMutation } from '@app/store/redux/formApi';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { usePathname, useRouter } from 'next/navigation';
import { toast } from 'react-toastify';

const PublishButton = ({ refresh = false }: { refresh?: boolean }) => {
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();
    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();
    const router = useRouter();
    const pathname = usePathname();
    const { authState } = useAuthAtom();

    const publishForm = async () => {
        const response: any = await publishV2Form({
            workspaceId: workspace.id,
            formId: standardForm.formId
        });

        if (response.data) {
            if (refresh && pathname) {
                router.push(pathname);
                toast('Form Published');
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
