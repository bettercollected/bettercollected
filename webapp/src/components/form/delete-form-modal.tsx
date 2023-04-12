import { useRouter } from 'next/router';

import { DeleteForever } from '@mui/icons-material';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteFormMutation } from '@app/store/workspaces/api';

import { useModal } from '../modal-views/context';
import Button from '../ui/button';

export default function DeleteFormModal(props: any) {
    const { closeModal } = useModal();

    const [trigger] = useDeleteFormMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();
    const form = useAppSelector((state) => state.form);
    const handleLogout = async () => {
        console.log(form.formId);
        const response: any = await trigger({ workspaceId: workspace.id, formId: form.formId });
        if (response?.data) {
            router.push(`/${workspace.workspaceName}/dashboard`);
        }
        if (response?.error) {
            toast('Could not delete form.', { type: 'error' });
        }
        // closeModal();
    };

    function DialogBox() {
        return (
            <>
                <h5 className="text-lg font-semibold leading-normal text-left ">Are you sure to delete this form?</h5>
                <div>This cannot be undone.</div>
                <div className="flex w-full gap-4 justify-between">
                    <Button data-testid="logout-button" variant="solid" className="!rounded-xl !m-0 !bg-red-500" onClick={handleLogout}>
                        Delete
                    </Button>
                    <Button variant="transparent" className="!rounded-xl  !m-0 !border-gray border-[1px] !border-solid" onClick={() => closeModal()}>
                        Cancel
                    </Button>
                </div>
            </>
        );
    }

    function ImageRenderer() {
        return (
            <div>
                <DeleteForever className="text-8xl text-red-500" />
            </div>
        );
    }

    function LogoutContainer() {
        const { closeModal } = useModal();

        return (
            <div className=" relative m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-110">
                <div className=" relative flex flex-col  items-center gap-8 justify-between p-10">
                    <ImageRenderer />
                    <DialogBox />
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        );
    }

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <LogoutContainer />
        </div>
    );
}
