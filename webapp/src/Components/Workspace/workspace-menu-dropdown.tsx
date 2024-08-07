import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { IconButton, ListItem, Typography } from '@mui/material';

import AuthAccountProfileImage from '@app/Components/auth/account-profile-image';
import ProPlanHoc from '@app/Components/HOCs/pro-plan-hoc';
import { Check } from '@app/Components/icons/check';
import { Plus } from '@app/Components/icons/plus';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import Loader from '@app/Components/ui/loader';
import environments from '@app/configs/environments';
import dashboardConstants from '@app/constants/locales/dashboard';
import { Features } from '@app/constants/locales/feature';
import { menuDropdown } from '@app/constants/locales/menu-dropdown';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { selectAuth, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { generateRandomBgColor } from '@app/utils/backgroundColors';
import { toEndDottedStr, trimTooltipTitle } from '@app/utils/stringUtils';

interface IWorkspaceMenuDropdownProps {
    fullWidth?: boolean;
}

WorkspaceMenuDropdown.defaultProps = {
    fullWidth: false
};

function WorkspaceMenuDropdown({ fullWidth }: IWorkspaceMenuDropdownProps) {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetAllMineWorkspacesQuery();
    const router = useRouter();
    const isProPlan = useAppSelector(selectIsProPlan);
    const { openModal } = useFullScreenModal();

    const { t } = useTranslation();
    const handleChangeWorkspace = (space: WorkspaceDto) => {
        if (!space?.disabled) router.push(`/${space.workspaceName}/dashboard/forms`);
    };
    const auth = useAppSelector(selectAuthStatus);
    const user = useAppSelector(selectAuth);

    const handleCreateWorkspace = () => {
        if (!enableCreateWorkspaceButton() || !isProPlan) {
            return;
        }
        router.push(`/workspace/create`);
    };

    const redirectToUpgradeIfNotProPlan = () => {
        if (!isProPlan) {
            openModal('UPGRADE_TO_PRO', {
                callback: () => {
                    router.push(`/workspace/create`);
                }
            });
        }
    };

    const fullWorkspaceName = workspace?.title || 'Untitled';
    const workspaceName = toEndDottedStr(fullWorkspaceName, 16);
    const showExpandMore = true;

    const enableCreateWorkspaceButton = () => {
        if (!data || isLoading || !Array.isArray(data)) {
            return false;
        }
        const usersWorkspaces = data.filter((space: WorkspaceDto) => {
            return space.ownerId === auth?.id;
        });
        return usersWorkspaces.length < environments.MAX_WORKSPACES;
    };

    const getWorkspaceRole = (space: WorkspaceDto) => {
        if (auth && space && auth?.id === space?.ownerId) return t(dashboardConstants.drawer.owner);
        return t(dashboardConstants.drawer.collaborator);
    };

    return (
        <MenuDropdown
            id="workspace-menu"
            menuTitle={trimTooltipTitle(fullWorkspaceName)}
            fullWidth={fullWidth}
            className={`hover:!bg-black-100 !rounded-lg ${showExpandMore ? 'pr-4' : ''}`}
            showExpandMore={showExpandMore}
            width={320}
            menuContent={
                <div className="flex w-[200px] items-center gap-2 px-3 py-1">
                    <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspace?.title || 'Untitled'} variant="circular" />
                    <div className="flex w-full flex-col items-start truncate">
                        <Typography className="body3 truncate">{toEndDottedStr(workspace?.title || 'Untitled', 14)}</Typography>

                        <p className="text-black-700 text-[12px] leading-none">{getWorkspaceRole(workspace)}</p>
                    </div>
                </div>
            }
        >
            {isLoading ? (
                <ListItem disablePadding className="flex items-center justify-center px-5 py-3" alignItems="center">
                    <Loader />
                </ListItem>
            ) : !!data && Array.isArray(data) ? (
                data.map((space: WorkspaceDto) => {
                    const color = generateRandomBgColor();
                    return (
                        <ListItem key={space.id} disablePadding alignItems="flex-start">
                            <IconButton
                                className={`hover:bg-black-100 rounded px-5 py-3 hover:rounded-none ${space?.disabled && 'cursor-not-allowed'} ${fullWidth ? 'flex w-full justify-between' : 'w-fit'}`}
                                onClick={() => handleChangeWorkspace(space)}
                                size="small"
                            >
                                <div className="flex w-full items-center justify-between gap-4">
                                    <div className="flex items-center gap-3">
                                        <AuthAccountProfileImage
                                            size={40}
                                            image={space?.profileImage}
                                            name={space?.title || 'Untitled'}
                                            className={color}
                                            // style={{ background: `${color} !important` }}
                                        />
                                        <div className="flex w-full flex-col items-start">
                                            <Tooltip title={trimTooltipTitle(space?.title)}>
                                                <p className="body3">{toEndDottedStr(space?.title || 'Untitled', 20)}</p>
                                            </Tooltip>
                                            <p className="text-black-700 text-[12px] leading-none">{getWorkspaceRole(space)}</p>
                                        </div>
                                    </div>
                                    {workspace.id === space.id && <Check color="#0764EB" />}
                                </div>
                            </IconButton>
                        </ListItem>
                    );
                })
            ) : (
                <ListItem disablePadding alignItems="center">
                    <IconButton className={`hover:bg-black-100 rounded px-5 py-3 ${fullWidth ? 'flex w-full justify-between' : 'w-fit'}`} onClick={() => handleChangeWorkspace(workspace)} size="small">
                        <div className="flex w-full items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} />
                                <div className="flex w-full flex-col items-start">
                                    <Tooltip title={trimTooltipTitle(fullWorkspaceName)}>
                                        <p className="body3">{workspaceName}</p>
                                    </Tooltip>
                                    <p className="text-black-700 text-[12px] leading-none">{getWorkspaceRole(workspace)}</p>
                                </div>
                            </div>
                            <Check color="#0764EB" />
                        </div>
                    </IconButton>
                </ListItem>
            )}
            {!isLoading && (
                <div>
                    <Divider className="my-2" />
                    <div>
                        <ListItem onClick={redirectToUpgradeIfNotProPlan} disablePadding alignItems="center" className={``}>
                            <IconButton
                                data-umami-event={'Create New Workspace Button'}
                                data-umami-event-email={user.email}
                                className={`hover:bg-black-100 rounded px-5 py-3 ${fullWidth ? 'flex w-full justify-between' : 'w-fit'} ${!enableCreateWorkspaceButton() && isProPlan ? '!text-black-500 cursor-not-allowed' : '!text-black-800'}`}
                                onClick={handleCreateWorkspace}
                                size="small"
                            >
                                <span className="flex w-full items-center justify-between gap-4">
                                    <div className="flex items-center gap-3">
                                        <Plus />
                                        <p className={`body3 !not-italic  `}>{t(menuDropdown.createWorkspace)}</p>
                                    </div>
                                </span>
                            </IconButton>
                        </ListItem>
                    </div>
                </div>
            )}
        </MenuDropdown>
    );
}

export default React.memo(WorkspaceMenuDropdown);
