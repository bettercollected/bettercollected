import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceDomainMutation, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

interface IUpdateWorkspaceSettings {
    updateDomain: boolean;
    customSlug?: string;
}

export default function UpdateWorkspaceSettings({ updateDomain = false, customSlug }: IUpdateWorkspaceSettings) {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const [deleteWorkspaceDomain, result] = useDeleteWorkspaceDomainMutation();
    const { t } = useTranslation();
    const { closeModal } = useModal();
    const [error, setError] = useState(false);

    const [updateText, setUpdateText] = useState(updateDomain ? workspace.customDomain || '' : workspace.workspaceName || '');
    const customDomain = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${updateText}/forms`;
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
                <div className="body1 mt-6">{updateDomain ? t(localesCommon.domain) : t(workspaceConstant.handle)}</div>
                <div className="mt-3 gap-2 md:gap-4 flex flex-col md:flex-row items-start md:items-center w-full">
                    <div className="flex flex-col items-start justify-start gap-1 w-full">
                        <AppTextField
                            isError={error}
                            dataTestId={'update-button'}
                            placeholder={updateDomain ? t(placeHolder.enterCustomDomain) : t(placeHolder.enterWorkspaceHandle)}
                            value={updateText}
                            onChange={(e) => {
                                setUpdateText(e.target.value);
                            }}
                        >
                            {customSlug && <AppTextField.Description>{`${customDomain}/${customSlug}`}</AppTextField.Description>}
                        </AppTextField>
                    </div>

                    <AppButton className="w-full" data-testid="save-button" type="submit" isLoading={isLoading || result?.isLoading} size={ButtonSize.Medium} variant={ButtonVariant.Primary} onClick={handleSubmit}>
                        {t(buttonConstant.updateNow)}
                    </AppButton>
                </div>
                <span className={'text-red-500 text-xs font-normal'}>{error ? (updateDomain ? t(updateWorkspace.invalidDomain) : t(updateWorkspace.invalidWorkspaceHandle)) : ''}</span>

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
