import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import Share from '@Components/Common/Icons/Share';
import { Button } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceDashboardStats from '@app/components/workspace-dashboard/workspace-dashboard-stats';
import environments from '@app/configs/environments';
import { formsConstant } from '@app/constants/locales/forms';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { toEndDottedStr } from '@app/utils/stringUtils';

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

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${language}${w_name}`;
    };

    const handleWorkspaceEllipsisClick = () => {};

    const importedFormsContent = (workspaceStats && workspaceStats?.forms ? `${workspaceStats.forms}` : `0`) + (isAdmin && !isProPlan ? '/100' : '');
    const importedResponses = workspaceStats && workspaceStats?.responses ? `${workspaceStats.responses}` : '0';
    const deletionRequests = workspaceStats && workspaceStats?.deletion_requests && workspaceStats.deletion_requests?.total ? `${workspaceStats.deletion_requests?.success || 0}/${workspaceStats.deletion_requests.total || 0}` : '0/0';

    const workspaceDashboardStatsList = [
        {
            key: 'imported-forms',
            className: JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_FORMS,
            title: t(formsConstant.importedForms),
            tooltipTitle: `${workspaceStats?.forms ?? 0} ${t(toolTipConstant.formImported)}${isAdmin && !isProPlan ? ` ${t(toolTipConstant.outOfLimited)}` : ''}`,
            content: importedFormsContent,
            buttonProps: {
                enabled: isAdmin && !isProPlan,
                text: t(formsConstant.importUnlimited),
                onClick: () => {
                    router.push(`/${workspace.workspaceName}/upgrade`);
                }
            }
        },
        {
            key: 'collected-responses',
            className: JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_RESPONSES,
            title: t(formsConstant.collectedResponses),
            tooltipTitle: `${workspaceStats?.responses ?? 0} ${t(toolTipConstant.formResponses)}`,
            content: importedResponses,
            buttonProps: {
                enabled: false,
                text: t(formsConstant.importUnlimited),
                onClick: () => {}
            }
        },
        {
            key: 'deletion-requests',
            className: JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_DELETION_REQUESTS,
            title: t(formsConstant.deletionRequests),
            tooltipTitle: `${workspaceStats?.deletion_requests?.success ?? 0} ${t(toolTipConstant.responseDeletionOutOf)} ${workspaceStats?.deletion_requests?.total ?? 0} ${t(toolTipConstant.deletionRequest)}`,
            content: deletionRequests,
            buttonProps: {
                enabled: false,
                text: t(formsConstant.importUnlimited),
                onClick: () => {}
            }
        }
    ];

    return (
        <>
            <div className="flex flex-col md:flex-row justify-center md:justify-start md:items-center mb-4">
                <div className={`flex items-center ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`}>
                    <AuthAccountProfileImage size={48} image={workspace?.profileImage} name={workspace?.title || 'Untitled'} className="bg-blend-darken	" />
                    <Tooltip title={workspace?.title}>
                        <h1 className="sh1 ml-3 h-12 flex items-center joyride-workspace-title">{toEndDottedStr(workspace?.title?.trim() || 'Untitled', 30)}</h1>
                    </Tooltip>
                </div>
                <div className="flex items-center gap-4 ml-0 mt-3 md:mt-0 md:ml-10 min-h-[28px]">
                    <Button
                        variant="text"
                        sx={{ minWidth: '24px', maxWidth: '48px' }}
                        onClick={() => openModal('SHARE_VIEW', { url: getWorkspaceUrl(), title: t(workspaceConstant.share) })}
                        className={`body4 rounded !leading-none hover:cursor-pointer capitalize ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`}
                    >
                        <Share />
                    </Button>
                    <ActiveLink href={getWorkspaceUrl()} target="_blank" referrerPolicy="origin">
                        <Tooltip title={t(toolTipConstant.previewWorkspace)}>
                            <Button variant="outlined" className={`body4 !leading-none !p-2 !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize ${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`}>
                                Preview
                            </Button>
                        </Tooltip>
                    </ActiveLink>

                    {/* <Tooltip title="Workspace settings">
                        <IconButton onClick={handleWorkspaceEllipsisClick} size="medium" className="rounded-[4px] text-black-900 hover:rounded-[4px] hover:bg-black-200">
                            <EllipsisOption />
                        </IconButton>
                    </Tooltip> */}
                </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-6">
                {workspaceDashboardStatsList.map((stat) => (
                    <WorkspaceDashboardStats key={stat.key} className={stat.className} title={stat.title} tooltipTitle={stat.tooltipTitle} content={stat.content} buttonProps={stat.buttonProps} />
                ))}
            </div>
            <Divider className="my-6" />
        </>
    );
};

export default WorkspaceDashboardOverview;
