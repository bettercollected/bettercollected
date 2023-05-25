import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import CopyIcon from '@Components/Common/Icons/Copy';
import Pro from '@Components/Common/Icons/Pro';
import { toast } from 'react-toastify';

import ProPlanHoc from '@app/components/hoc/pro-plan-hoc';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
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

    const urlText = environments.HTTP_SCHEME + (updateDomain ? workspace.customDomain : environments.CLIENT_DOMAIN + '/' + workspace.workspaceName);

    const handleClick = () => {
        if (type === 'DOMAIN' && isProPlan) {
            openModal('UPDATE_WORKSPACE_DOMAIN');
        } else if (type === 'HANDLE') {
            openModal('UPDATE_WORKSPACE_HANDLE');
        }
    };

    return (
        <SettingsCard className={`!mt-5 relative ${!isProPlan && updateDomain ? '!bg-brand-200' : ''}`}>
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
                        <div className="flex flex-col md:flex-row space-y-4 md:space-y-0 md:items-center space-between">
                            <div className="flex items-center flex-1">
                                <div className="px-2 body6 py-3 w-full border border-black-400 rounded mr-2">
                                    {updateDomain && workspace.customDomain ? (
                                        <>
                                            <span className="text-black-700">{environments.HTTP_SCHEME}</span>
                                            <span className="text-black-900">{workspace.customDomain}</span>
                                        </>
                                    ) : (
                                        <>
                                            <span className="text-black-700">
                                                {environments.HTTP_SCHEME}
                                                {environments.CLIENT_DOMAIN}
                                            </span>
                                            /<span className="text-black-900">{workspace?.workspaceName}</span>
                                        </>
                                    )}
                                </div>
                                <Tooltip title="Copy Link">
                                    <CopyIcon
                                        className="cursor-pointer mr-4"
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
                                <Button disabled={!isProPlan && updateDomain} onClick={handleClick}>
                                    {t(updateWorkspace.common.change)}
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            {!isProPlan && updateDomain && (
                <>
                    <div className="flex items-center">
                        <span className="mr-1 font-semibold">Upgrade to PRO</span> for this feature
                        <ProPlanHoc hideChildrenIfPro={false}>
                            <Button className="ml-4">Upgrade</Button>
                        </ProPlanHoc>
                    </div>
                    <div className="absolute !top-2 !right-5">
                        <div className="flex items-center rounded h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                            <Pro width={12} height={12} />
                            <span className="leading-none">Pro</span>
                        </div>
                    </div>
                </>
            )}
        </SettingsCard>
    );
}
