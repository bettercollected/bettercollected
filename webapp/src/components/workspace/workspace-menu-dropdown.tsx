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
import { menuDropdown } from '@app/constants/locales/menu-dropdown';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IWorkspaceMenuDropdownProps {
    fullWidth?: boolean;
}

WorkspaceMenuDropdown.defaultProps = {
    fullWidth: false
};
export default function WorkspaceMenuDropdown({ fullWidth }: IWorkspaceMenuDropdownProps) {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetAllMineWorkspacesQuery();
    const router = useRouter();
    const language = router?.locale === 'en' ? '' : router?.locale;

    const { t } = useTranslation();
    const handleChangeWorkspace = (space: WorkspaceDto) => {
        router.push(`/${space.workspaceName}/dashboard`);
    };

    const handleCreateWorkspace = () => {
        if (!isLoading && data?.length > 2) {
            return;
        }
        router.push(`/${language}create-workspace`);
    };

    const fullWorkspaceName = workspace?.title || workspace?.workspaceName || '';
    const workspaceName = toEndDottedStr(fullWorkspaceName, 15);
    const showExpandMore = true;

    return (
        <MenuDropdown
            id="workspace-menu"
            menuTitle={fullWorkspaceName}
            fullWidth={fullWidth}
            className={`!rounded-none hover:!rounded-none ${showExpandMore ? 'pr-4' : ''}`}
            showExpandMore={showExpandMore}
            menuContent={
                <div className="flex items-center gap-2 py-2 px-3">
                    <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} />
                    <p className="body1">{workspaceName}</p>
                </div>
            }
        >
            {isLoading ? (
                <ListItem disablePadding className="px-5 py-3 flex justify-center items-center" alignItems="center">
                    <Loader />
                </ListItem>
            ) : !!data && Array.isArray(data) ? (
                data.map((space: WorkspaceDto) => (
                    <ListItem key={space.id} disablePadding alignItems="flex-start">
                        <IconButton className={`px-5 py-3 rounded hover:rounded-none hover:bg-brand-100 ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={() => handleChangeWorkspace(space)} size="small">
                            <div className="flex justify-between w-full items-center gap-4">
                                <div className="flex items-center gap-3">
                                    <AuthAccountProfileImage size={40} image={space?.profileImage} name={space?.title} />
                                    <Tooltip title={space?.title}>
                                        <p className="body3">{toEndDottedStr(space?.title, 15)}</p>
                                    </Tooltip>
                                </div>
                                {workspace.id === space.id && <Check color="#0764EB" />}
                            </div>
                        </IconButton>
                    </ListItem>
                ))
            ) : (
                <ListItem disablePadding alignItems="center">
                    <IconButton className={`px-5 py-3 rounded hover:rounded-none hover:bg-brand-100 ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={() => handleChangeWorkspace(workspace)} size="small">
                        <div className="flex justify-between w-full items-center gap-4">
                            <div className="flex items-center gap-3">
                                <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} />
                                <Tooltip title={fullWorkspaceName}>
                                    <p className="body3">{workspaceName}</p>
                                </Tooltip>
                            </div>
                            <Check color="#0764EB" />
                        </div>
                    </IconButton>
                </ListItem>
            )}
            {!isLoading && (
                <div>
                    <Divider className="my-2" />
                    <ListItem disablePadding alignItems="center">
                        <IconButton className={`px-5 py-3 rounded hover:rounded-none hover:bg-brand-100 ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={handleCreateWorkspace} size="small">
                            <span className="flex justify-between w-full items-center gap-4">
                                <div className="flex items-center gap-3">
                                    <Plus className="text-black-500" />
                                    <p className={`body3 !not-italic ${!isLoading && data?.length > 2 ? '!text-black-500 cursor-not-allowed' : '!text-black-800'} `}>{t(menuDropdown.createWorkspace)}</p>
                                </div>
                            </span>
                        </IconButton>
                    </ListItem>
                </div>
            )}
        </MenuDropdown>
    );
}
