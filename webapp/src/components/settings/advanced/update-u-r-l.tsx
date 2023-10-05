import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import CopyIcon from '@Components/Common/Icons/Copy';
import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import UpgradeToPro from '@app/components/ui/upgrade-to-pro';
import environments from '@app/configs/environments';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface IUpdateURLProps {
    type: 'DOMAIN' | 'HANDLE';
}

export default function UpdateURL({ type }: IUpdateURLProps) {
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();
    const { t } = useTranslation();
    const updateDomain = type === 'DOMAIN';
    const isProPlan = useAppSelector(selectIsProPlan);
    const [_, copyToClipboard] = useCopyToClipboard();

    const urlText = environments.HTTP_SCHEME + (updateDomain && isProPlan && workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN + '/' + workspace.workspaceName);

    const handleClick = () => {
        if (type === 'DOMAIN' && isProPlan) {
            openModal('UPDATE_WORKSPACE_DOMAIN');
        } else if (type === 'HANDLE') {
            openModal('UPDATE_WORKSPACE_HANDLE');
        }
    };

    return (
        <SettingsCard className={`!mt-5 relative p-5 lg:p-10 ${!isProPlan && updateDomain ? '!bg-brand-200' : ''}`}>
            <div className="sh3">{updateDomain ? t(workspaceConstant.customDomain) : t(workspaceConstant.handle)}</div>
            <div className="flex flex-col w-full justify-between">
                <div className="w-full text-sm mb-10 text-black-700">{updateDomain ? t(updateWorkspace.domain.desc) : t(updateWorkspace.handles.desc)}</div>
                <div className="w-full body6 mb-4 !font-semibold text-black-900">{t(updateWorkspace.common.consequence)}</div>
                <ul className="list-disc body4 ml-10 mb-10">
                    <li className="mb-4">{updateDomain ? t(updateWorkspace.domain.point1) : t(updateWorkspace.handles.point1)}</li>
                    <li>{updateDomain ? t(updateWorkspace.domain.point2) : t(updateWorkspace.handles.point2)}</li>
                </ul>
                <div className="flex space-between items-end w-full">
                    <div className="flex-1">
                        <div className="body6 mb-6 font-semibold">{t(updateWorkspace.common.currentLink)}</div>
                        <div className="flex flex-col md:flex-row gap-4 space-y-4 md:space-y-0 md:items-center space-between">
                            <div className="flex items-center gap-4 max-w-full flex-1">
                                <AppTextField className="w-full" isDisabled value={environments.HTTP_SCHEME + (updateDomain && isProPlan && workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN + '/' + workspace.workspaceName)} />
                                <Tooltip title={t(toolTipConstant.copyLink)}>
                                    <CopyIcon
                                        className={isProPlan || type === 'HANDLE' ? 'cursor-pointer' : 'cursor-not-allowed pointer-events-none'}
                                        onClick={() => {
                                            copyToClipboard(urlText);
                                            toast('Copied', {
                                                type: 'info'
                                            });
                                        }}
                                    />
                                </Tooltip>
                            </div>
                            <div>
                                <AppButton size={ButtonSize.Medium} disabled={!isProPlan && updateDomain} onClick={handleClick}>
                                    {t(updateWorkspace.common.change)}
                                </AppButton>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            {!isProPlan && updateDomain && <UpgradeToPro />}
        </SettingsCard>
    );
}
