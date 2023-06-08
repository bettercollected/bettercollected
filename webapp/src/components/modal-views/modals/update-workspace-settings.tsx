import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import { buttonConstant } from '@app/constants/locales/button';
import { localesGlobal } from '@app/constants/locales/global';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceDomainMutation, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function UpdateWorkspaceSettings({ updateDomain = false }: { updateDomain: boolean }) {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const [deleteWorkspaceDomain, result] = useDeleteWorkspaceDomainMutation();
    const { t } = useTranslation();
    const { closeModal } = useModal();
    const [error, setError] = useState(false);

    const [updateText, setUpdateText] = useState(updateDomain ? workspace.customDomain || '' : workspace.workspaceName || '');

    const dispatch = useAppDispatch();

    const router = useRouter();
    const { openModal } = useModal();

    useEffect(() => {
        if (updateDomain) {
            setError(!!updateText && !updateText.match('(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|([a-zA-Z0-9][a-zA-Z0-9-_]{1,61}[a-zA-Z0-9]))\\.([a-zA-Z]{2,6}|[a-zA-Z0-9-]{2,30}\\.[a-zA-Z]{2,3})'));
        } else {
            setError(!updateText.match(/^(?=.*$)(?![_.])(?!.*[_.]{2})[a-zA-Z0-9._]+(?<![_.])$/));
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
            toast.info(updateDomain ? t(toastMessage.customDomainUpdated).toString() : t(updateWorkspace.handle).toString(), { toastId: ToastId.SUCCESS_TOAST });
            if (!updateDomain) {
                router.replace(`/${response.data.workspaceName}/dashboard`);
            }
            closeModal();
        } else if (response.error) {
            toast.error(response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), { toastId: ToastId.ERROR_TOAST });
        }
    };

    const handleResetClick = () => {
        openModal('DELETE_CUSTOM_DOMAIN');
    };

    return (
        <div className="w-full !bg-brand-100 relative  rounded-lg shadow-md p-10  max-w-[502px] sm:max-w-lg md:max-w-xl">
            <Close
                className="absolute cursor-pointer top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="flex space-x-4">
                <div className="sh1 mb-6 leading-tight tracking-tight md:text-2xl text-black-900">{updateDomain ? (workspace.customDomain ? t(updateWorkspace.customDomain) : t(updateWorkspace.setupCustomDomain)) : t(updateWorkspace.handle)}</div>
            </div>
            <form className="flex items-start flex-col">
                <div className="text-start max-w-full">
                    <ul className="list-disc ml-10">
                        <li>{t(updateWorkspace.settings.common.point1)}</li>
                        <li>{t(updateWorkspace.settings.common.point2)}</li>
                        <li>{t(updateWorkspace.settings.common.point3)}</li>
                        {!updateDomain && <li>{t(updateWorkspace.settings.handle.point4)}</li>}
                    </ul>
                </div>
                <div className="mt-4">{updateDomain && t(updateWorkspace.settings.domain.cname) + 'custom.bettercollected.com'}</div>
                <div className="body1 mt-6">{updateDomain ? t(localesGlobal.domain) : t(workspaceConstant.handle)}</div>
                <div className="mt-3 flex flex-col md:flex-row md:items-start w-full">
                    <div className="flex items-start justify-start gap-4  w-full">
                        <BetterInput
                            inputProps={{ 'data-testid': 'update-field', className: 'bg-white !py-3' }}
                            error={error}
                            helperText={error ? (updateDomain ? t(updateWorkspace.invalidDomain) : t(updateWorkspace.invalidWorkspaceHandle)) : ''}
                            placeholder={updateDomain ? t(placeHolder.enterCustomDomain) : t(placeHolder.enterWorkspaceHandle)}
                            value={updateText}
                            onChange={(e) => {
                                setUpdateText(e.target.value);
                            }}
                            className="font-bold flex-1 w-full"
                        />
                    </div>
                    <Button data-testid="save-button" type="submit" isLoading={isLoading || result?.isLoading} variant="solid" size="medium" onClick={handleSubmit} className="md:ml-4 flex-1 min-w-fit">
                        {t(buttonConstant.updateNow)}
                    </Button>
                </div>

                {workspace.customDomain && updateDomain && (
                    <div className="mt-4">
                        {t(updateWorkspace.settings.domain.remove)}{' '}
                        <span onClick={handleResetClick} className="ml-1 cursor-pointer text-brand-500 underline">
                            {t(updateWorkspace.settings.domain.reset)}{' '}
                        </span>
                    </div>
                )}
            </form>
        </div>
    );
}
