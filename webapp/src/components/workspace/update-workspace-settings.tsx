import { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import { DeleteOutline } from '@mui/icons-material';
import { TextField } from '@mui/material';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceDomainMutation, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

import Button from '../ui/button/button';

export default function UpdateWorkspaceSettings({ updateDomain = false }: { updateDomain: boolean }) {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const [deleteWorkspaceDomain, result] = useDeleteWorkspaceDomainMutation();
    const { closeModal } = useModal();
    const [error, setError] = useState(false);

    const [updateText, setUpdateText] = useState(updateDomain ? workspace.customDomain || '' : workspace.workspaceName || '');

    const dispatch = useAppDispatch();

    const router = useRouter();

    useEffect(() => {
        if (updateDomain) {
            setError(!!updateText && !updateText.match('(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|([a-zA-Z0-9][a-zA-Z0-9-_]{1,61}[a-zA-Z0-9]))\\.([a-zA-Z]{2,6}|[a-zA-Z0-9-]{2,30}\\.[a-zA-Z]{2,3})'));
        } else {
            setError(!updateText);
        }
    }, [updateText]);

    const handleSubmit = async (e: any) => {
        e.preventDefault();
        if (error) return;
        if (!updateText && !updateDomain) return;
        const formData = new FormData();
        if (updateDomain && updateText === workspace.customDomain) {
            closeModal();
            return;
        }
        if (!updateDomain && updateText === workspace.workspaceName) {
            closeModal();
            return;
        }
        if (updateDomain) {
            formData.append('custom_domain', updateText);
        } else {
            formData.append('workspace_name', updateText);
        }
        const body = {
            workspace_id: workspace.id,
            body: formData
        };
        const response: any = await patchExistingWorkspace(body);
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast.info(updateDomain ? 'Updated custom Domain of workspace!' : 'Updated workspace handle', { toastId: ToastId.SUCCESS_TOAST });
            if (!updateDomain) {
                router.replace(`/${response.data.workspaceName}/dashboard`);
            }
            closeModal();
        } else if (response.error) {
            toast.error(response.error.data?.message || 'Something went wrong', { toastId: ToastId.ERROR_TOAST });
        }
    };

    const delete_custom_domain = async (e: any) => {
        e.preventDefault();
        const res: any = await deleteWorkspaceDomain(workspace.id);
        if (res.data) {
            dispatch(setWorkspace(res.data));
            router.push(router.asPath);
        } else {
            toast.error('Error Deleting Custom Domain');
        }
    };

    return (
        <div className="w-full relative bg-white rounded-lg shadow-md p-10  max-w-[502px] sm:max-w-lg md:max-w-xl">
            <Close
                className="absolute cursor-pointer top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="flex space-x-4">
                <div className="sh1 mb-6 leading-tight tracking-tight md:text-2xl text-black-900">{updateDomain ? (workspace.customDomain ? 'Update your Custom Domain' : 'Setup your custom domain for workspace') : 'Update Workspace Handle'}</div>
            </div>
            <form className="flex items-start flex-col">
                <div className="text-start max-w-full">
                    <div className="body-3 text-black-700 ">
                        {updateDomain
                            ? workspace?.customDomain
                                ? "Form links with previous domain won't work after updating."
                                : `Add CNAME record of your domain to point to 'custom.${environments.IS_IN_PRODUCTION_MODE ? 'bettercollected.com' : 'sireto.dev'}'`
                            : "Form links with previous workspace handle won't work after updating."}
                    </div>
                </div>
                <div className="body1 mt-6">{updateDomain ? 'Domain' : 'Workspace Handle'}</div>
                <div className="flex items-start mt-3 justify-start gap-4  w-full">
                    <BetterInput
                        inputProps={{ 'data-testid': 'update-field' }}
                        error={error}
                        helperText={error ? (updateDomain ? 'Invalid domain' : 'Invalid Workspace Handle') : ''}
                        placeholder={updateDomain ? 'Enter your custom domain' : 'Enter workspace handle'}
                        value={updateText}
                        onChange={(e) => {
                            setUpdateText(e.target.value);
                        }}
                        className="font-bold w-full"
                    />
                    {workspace.customDomain && updateDomain && (
                        <button data-testid="delete-button" type="button" onClick={delete_custom_domain}>
                            <DeleteOutline className="text-red-500 mt-2 bg-red-100 h-[35px] w-[35px] rounded p-1.5" />
                        </button>
                    )}
                </div>
                <div className="flex mt-8 w-full gap-4 justify-end">
                    <Button data-testid="save-button" type="submit" isLoading={isLoading || result?.isLoading} variant="solid" size="medium" onClick={handleSubmit}>
                        Save
                    </Button>
                </div>
            </form>
        </div>
    );
}
