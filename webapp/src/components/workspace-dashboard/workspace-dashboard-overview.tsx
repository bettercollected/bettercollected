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
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import dashboardConstants from '@app/constants/locales/dashboard';
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

interface IWorkspaceDashboardOverviewProps {
    workspace: WorkspaceDto;
    workspaceStats: {
        forms: number;
        responses: number;
        deletion_requests: { success: number; pending: number; total: number };
    };
}

const WorkspaceDashboardOverview = ({ workspace, workspaceStats }: IWorkspaceDashboardOverviewProps) => {
    const { openModal } = useModal();
    const isProPlan = useAppSelector(selectIsProPlan);
    const isAdmin = useAppSelector(selectIsAdmin);
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
        <>
            <div className="flex flex-col md:flex-row justify-center md:justify-between  md:items-center mb-4 bg-white rounded p-4">
                <div className="flex">
                    <div className={`flex items-center ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`}>
                        <AuthAccountProfileImage size={48} image={workspace?.profileImage} name={workspace?.title || 'Untitled'} className="bg-blend-darken	" />
                        <Tooltip title={workspace?.title}>
                            <h1 className="sh1 ml-3 h-12 flex items-center joyride-workspace-title">{toEndDottedStr(workspace?.title?.trim() || 'Untitled', 30)}</h1>
                        </Tooltip>
                    </div>
                    <div className="flex items-center gap-3 ml-0 mt-3 space-x-3 md:mt-0 md:ml-10 min-h-[28px]">
                        <ActiveLink className="hover:bg-brand-100 rounded p-2" href={`/${workspace.workspaceName}/manage`}>
                            <EditIcon />
                        </ActiveLink>

                        <ActiveLink href={getWorkspaceUrl()} target="_blank" referrerPolicy="origin">
                            <Tooltip title={t(toolTipConstant.previewWorkspace)}>
                                <Button variant="outlined" className={`body4 !leading-none !p-2 !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`}>
                                    {t(dashboardConstants.preview)}
                                </Button>
                            </Tooltip>
                        </ActiveLink>
                        <div
                            onClick={() =>
                                openModal('SHARE_VIEW', {
                                    url: getWorkspaceUrl(),
                                    title: t(workspaceConstant.share)
                                })
                            }
                            className={`body4 rounded hover:bg-brand-100 p-2 !leading-none mr-4 hover:cursor-pointer capitalize ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`}
                        >
                            <Share />
                        </div>
                    </div>
                </div>
                <div className="flex space-x-[1px]">
                    <div
                        className="rounded bg-black-300 items-center cursor-pointer justify-center flex h-10 w-10"
                        onClick={() => {
                            openModal('INVITE_MEMBER');
                        }}
                    >
                        <PlusIcon />
                    </div>
                    {data?.map((user: UserDto) => (
                        <div key={user.email}>
                            <AuthAccountProfileImage image={user.profile_image} name={getFullNameFromUser(user)} size={40} />
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
};

export default WorkspaceDashboardOverview;
