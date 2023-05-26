import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { IconButton, ListItem } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { Check } from '@app/components/icons/check';
import { Plus } from '@app/components/icons/plus';
import Loader from '@app/components/ui/loader';
import dashboardConstants from '@app/constants/locales/dashboard';
import { menuDropdown } from '@app/constants/locales/menu-dropdown';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { generateRandomBgColor } from '@app/utils/backgroundColors';
import { toEndDottedStr } from '@app/utils/stringUtils';

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

    const { t } = useTranslation();
    const handleChangeWorkspace = (space: WorkspaceDto) => {
        if (!space?.disabled) router.push(`/${space.workspaceName}/dashboard`);
    };
    const auth = useAppSelector(selectAuthStatus);

    const handleCreateWorkspace = () => {
        if (!enableCreateWorkspaceButton() || !isProPlan) {
            return;
        }
        router.push(`/workspace/create`);
    };

    const redirectToUpgradeIfNotProPlan = () => {
        if (!isProPlan) {
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };

    const fullWorkspaceName = workspace?.title || 'Untitled';
    const workspaceName = toEndDottedStr(fullWorkspaceName, 19);
    const showExpandMore = true;

    const enableCreateWorkspaceButton = () => {
        if (!data || isLoading || !Array.isArray(data)) {
            return false;
        }
        const usersWorkspaces = data.filter((space: WorkspaceDto) => {
            return space.ownerId === auth?.id;
        });
        return usersWorkspaces.length < 3;
    };

    const getWorkspaceRole = (space: WorkspaceDto) => {
        if (auth && space && auth?.id === space?.ownerId) return t(dashboardConstants.drawer.owner);
        return t(dashboardConstants.drawer.collaborator);
    };

    return (
        <MenuDropdown
            id="workspace-menu"
            menuTitle={fullWorkspaceName}
            fullWidth={fullWidth}
            className={`!rounded-none hover:!rounded-none ${showExpandMore ? 'pr-4' : ''}`}
            showExpandMore={showExpandMore}
            menuContent={
                <div className="flex items-center gap-2 py-2 px-3">
                    <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} className="bg-orange-500" />
                    <p className="body1">{workspaceName}</p>
                </div>
            }
        >
            {isLoading ? (
                <ListItem disablePadding className="px-5 py-3 flex justify-center items-center" alignItems="center">
                    <Loader />
                </ListItem>
            ) : !!data && Array.isArray(data) ? (
                data.map((space: WorkspaceDto) => {
                    const color = generateRandomBgColor();
                    return (
                        <ListItem key={space.id} disablePadding alignItems="flex-start">
                            <IconButton
                                className={`px-5 py-3 rounded hover:rounded-none hover:bg-brand-100 ${space?.disabled && 'cursor-not-allowed'} ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`}
                                onClick={() => handleChangeWorkspace(space)}
                                size="small"
                            >
                                <div className="flex justify-between w-full items-center gap-4">
                                    <div className="flex items-center gap-3">
                                        <AuthAccountProfileImage
                                            size={40}
                                            image={space?.profileImage}
                                            name={space?.title || 'Untitled'}
                                            className={color}
                                            // style={{ background: `${color} !important` }}
                                        />
                                        <div className="flex flex-col items-start w-full">
                                            <Tooltip title={space?.title || 'Untitled'}>
                                                <p className="body3">{toEndDottedStr(space?.title || 'Untitled', 19)}</p>
                                            </Tooltip>
                                            <p className="leading-none text-[12px] text-black-700">{getWorkspaceRole(space)}</p>
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
                    <IconButton className={`px-5 py-3 rounded hover:rounded-none hover:bg-brand-100 ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={() => handleChangeWorkspace(workspace)} size="small">
                        <div className="flex justify-between w-full items-center gap-4">
                            <div className="flex items-center gap-3">
                                <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} />
                                <div className="flex flex-col items-start w-full">
                                    <Tooltip title={fullWorkspaceName}>
                                        <p className="body3">{workspaceName}</p>
                                    </Tooltip>
                                    <p className="leading-none text-[12px] text-black-700">{getWorkspaceRole(workspace)}</p>
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
                    <div onClick={redirectToUpgradeIfNotProPlan}>
                        <ListItem disablePadding alignItems="center" className={``}>
                            <IconButton
                                className={`px-5 py-3 rounded hover:rounded-none hover:bg-brand-100 ${fullWidth ? 'w-full flex justify-between' : 'w-fit'} ${
                                    !enableCreateWorkspaceButton() && isProPlan ? '!text-black-500 cursor-not-allowed' : '!text-black-800'
                                }`}
                                onClick={handleCreateWorkspace}
                                size="small"
                            >
                                <span className="flex justify-between w-full items-center gap-4">
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
