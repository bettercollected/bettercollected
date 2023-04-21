import { MoreHoriz } from '@mui/icons-material';
import { Divider, IconButton, Tooltip } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import WorkspaceDashboardStats from '@app/components/workspace-dashboard/workspace-dashboard-stats';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IWorkspaceDashboardOverviewProps {
    workspace: WorkspaceDto;
    workspaceStats: { forms: number; responses: number; deletion_requests: { success: number; pending: number; total: number } };
}

const WorkspaceDashboardOverview = ({ workspace, workspaceStats }: IWorkspaceDashboardOverviewProps) => {
    const { openModal } = useModal();

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    const handleWorkspaceEllipsisClick = () => {};

    const importedFormsContent = workspaceStats && workspaceStats?.forms ? `${workspaceStats.forms}/10` : `0/10`;
    const importedResponses = workspaceStats && workspaceStats?.responses ? `${workspaceStats.responses}` : '0';
    const deletionRequests =
        workspaceStats && workspaceStats?.deletion_requests && workspaceStats.deletion_requests?.total && workspaceStats.deletion_requests?.success ? `${workspaceStats.deletion_requests.success}/${workspaceStats.deletion_requests.total}` : '0/0';

    return (
        <>
            <div className="flex flex-col md:flex-row justify-center md:justify-start md:items-center mb-4">
                <div className="flex items-center">
                    <AuthAccountProfileImage size={48} image={workspace?.profileImage} name={workspace?.title} />
                    <Tooltip title={workspace?.title} arrow placement="top-start" enterDelay={300}>
                        <h1 className="sh1 ml-3">{toEndDottedStr(workspace?.title?.trim(), 30)}</h1>
                    </Tooltip>
                </div>
                <div className="flex items-center gap-3 ml-0 mt-3 md:mt-0 md:ml-10 min-h-[28px]">
                    <ActiveLink href={getWorkspaceUrl()}>
                        <Tooltip title="Preview your workspace" arrow placement="top-start" enterDelay={300}>
                            <IconButton size="medium" className="rounded-[4px] text-brand-500 hover:rounded-[4px] hover:bg-brand-200">
                                <EyeIcon height={22} width={22} />
                            </IconButton>
                        </Tooltip>
                    </ActiveLink>
                    <Button onClick={() => openModal('SHARE_VIEW', { url: getWorkspaceUrl() })} variant="solid" className="!text-brand-500 !border-blue-200 hover:!bg-brand-200">
                        Share
                    </Button>
                    <Tooltip title="Workspace settings" arrow placement="top-start" enterDelay={300}>
                        <IconButton onClick={handleWorkspaceEllipsisClick} size="medium" className="rounded-[4px] text-black-900 hover:rounded-[4px] hover:bg-black-200">
                            <MoreHoriz />
                        </IconButton>
                    </Tooltip>
                </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-6">
                <WorkspaceDashboardStats
                    title="Imported forms"
                    content={importedFormsContent}
                    buttonProps={{
                        enabled: true,
                        text: 'Import unlimited forms',
                        onClick: () => {}
                    }}
                />
                <WorkspaceDashboardStats
                    title="Collected responses"
                    content={importedResponses}
                    buttonProps={{
                        enabled: false,
                        text: 'Import unlimited forms',
                        onClick: () => {}
                    }}
                />
                <WorkspaceDashboardStats
                    title="Deletion requests"
                    content={deletionRequests}
                    buttonProps={{
                        enabled: false,
                        text: 'Import unlimited forms',
                        onClick: () => {}
                    }}
                />
            </div>
            <Divider className="my-6" />
        </>
    );
};

export default WorkspaceDashboardOverview;
