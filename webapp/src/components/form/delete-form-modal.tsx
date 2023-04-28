import { useRouter } from 'next/router';

import { DeleteForever } from '@mui/icons-material';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteFormMutation } from '@app/store/workspaces/api';

export default function DeleteFormModal(props: any) {
    const { closeModal } = useModal();

    const [trigger] = useDeleteFormMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();

    const handleDelete = async () => {
        const response: any = await trigger({ workspaceId: workspace.id, formId: props?.form.formId }).finally(() => closeModal());
        if (response?.data && !!props?.redirectToDashboard) {
            router.push(`/${workspace.workspaceName}/dashboard`);
        }
        if (response?.error) {
            toast('Could not delete form.', { type: 'error' });
        }
    };

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-center gap-8 justify-between p-10">
                    <DeleteForever className="text-6xl text-red-500" />
                    <div>
                        <h4 className="sh1 text-center">Are you sure you want to delete this form?</h4>
                        <p className="!text-black-600 body4 text-center leading-none">Once this action is completed, it can&apos;t be undone.</p>
                    </div>
                    <div className="flex w-full gap-4 justify-end">
                        <Button variant="solid" color="gray" size="medium" className="!bg-black-500" onClick={() => closeModal()}>
                            Cancel
                        </Button>
                        <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleDelete}>
                            Delete
                        </Button>
                    </div>
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        </div>
    );
}
