import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import EditIcon from '@Components/Common/Icons/Edit';
import PlusIcon from '@Components/Common/Icons/Plus';
import Share from '@Components/Common/Icons/Share';
import { Button } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import dashboardConstants from '@app/constants/locales/dashboard';
import { Features } from '@app/constants/locales/feature';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { UserDto } from '@app/models/dtos/UserDto';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { toEndDottedStr } from '@app/utils/stringUtils';
import { getFullNameFromUser } from '@app/utils/userUtils';

import ProPlanHoc from '../hoc/pro-plan-hoc';

interface IWorkspaceDashboardOverviewProps {
    workspace: WorkspaceDto;
}

const WorkspaceDashboardOverview = ({ workspace }: IWorkspaceDashboardOverviewProps) => {
    const { openModal } = useModal();
    const fullScreenModal = useFullScreenModal();
    const isAdmin = useAppSelector(selectIsAdmin);
    const isProPlan = useAppSelector(selectIsProPlan);
    const router = useRouter();
    const { t } = useTranslation();
    const language = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const { data } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${language}${w_name}`;
    };

    return (
        <div className="flex flex-col md:flex-row gap-6 justify-center md:justify-between md:items-center mb-9 bg-white rounded-lg shadow-formCard p-4">
            <div className="flex flex-col md:flex-row w-fit">
                <div className={`flex items-center ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`}>
                    <AuthAccountProfileImage size={48} image={workspace?.profileImage} name={workspace?.title || 'Untitled'} className="bg-blend-darken	" />
                    <Tooltip title={workspace?.title}>
                        <h1 className="sh1 ml-3 h-12 flex items-center joyride-workspace-title">{toEndDottedStr(workspace?.title?.trim() || 'Untitled', 30)}</h1>
                    </Tooltip>
                </div>
            </div>
            <div className="flex flex-row justify-between items-center flex-1">
                <div className="flex items-center gap-3 ml-0 md:mt-0 min-h-12">
                    {isAdmin && (
                        <div className={`flex items-center justify-center h-12 ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_EDIT}`}>
                            <div className="hover:bg-brand-100 rounded p-2 cursor-pointer" onClick={() => openModal('EDIT_WORKSPACE_MODAL')}>
                                <EditIcon />
                            </div>
                        </div>
                    )}

                    <div className={`flex items-center justify-center h-12 ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`}>
                        {/*<ActiveLink href={getWorkspaceUrl()} target="_blank" referrerPolicy="origin">*/}
                        <Tooltip title={t(toolTipConstant.previewWorkspace)}>
                            <Button
                                variant="outlined"
                                className="body4 !leading-none !p-2 !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize"
                                onClick={() => {
                                    fullScreenModal.openModal('WORKSPACE_PREVIEW');
                                }}
                            >
                                {t(dashboardConstants.preview)}
                            </Button>
                        </Tooltip>
                        {/*</ActiveLink>*/}
                    </div>
                    <div className={`flex items-center justify-center h-12 ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`}>
                        <div
                            onClick={() =>
                                openModal('SHARE_VIEW', {
                                    url: getWorkspaceUrl(),
                                    title: t(workspaceConstant.share)
                                })
                            }
                            className="body4 rounded hover:bg-brand-100 p-2 !leading-none hover:cursor-pointer capitalize"
                        >
                            <Share />
                        </div>
                    </div>
                </div>
                {isAdmin && (
                    <div className={`space-x-[1px] hidden sm:flex min-h-12 ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_COLLABORATORS}`}>
                        <ProPlanHoc feature={Features.collaborator}>
                            <div
                                className="rounded bg-black-300 items-center cursor-pointer justify-center flex h-10 w-10"
                                onClick={(event: any) => {
                                    if (isProPlan) openModal('INVITE_MEMBER');
                                }}
                            >
                                <PlusIcon />
                            </div>
                        </ProPlanHoc>
                        {data?.map((user: UserDto) => (
                            <div key={user.email}>
                                <AuthAccountProfileImage image={user.profile_image} name={getFullNameFromUser(user)} size={40} />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default WorkspaceDashboardOverview;
