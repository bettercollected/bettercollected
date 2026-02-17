'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';
import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { IconButton, ListItem, Typography } from '@mui/material';
import AuthAccountProfileImage from '@app/Components/auth/account-profile-image';
import { Check } from '@app/Components/icons/check';
import { Plus } from '@app/Components/icons/plus';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import Loader from '@app/Components/ui/loader';
import environments from '@app/configs/environments';
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

export default function WorkspaceMenuDropdownApp({ fullWidth = false }: IWorkspaceMenuDropdownProps) {
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

    if (isLoading) return <Loader />;

    return (
        <MenuDropdown
            fullWidth={fullWidth}
            className="!rounded-xl border border-black-200"
            trigger={
                <div className={`flex items-center gap-3 px-3 py-2 ${fullWidth ? 'w-full justify-between' : ''}`}>
                    <div className="flex items-center gap-2 overflow-hidden">
                        <div
                            className="flex h-6 w-5 min-w-[20px] items-center justify-center rounded text-[10px] font-bold text-white uppercase"
                            style={{ backgroundColor: generateRandomBgColor(workspace?.workspaceName || '') }}
                        >
                            {workspace?.workspaceName?.charAt(0)}
                        </div>
                        <Typography variant="body2" className="truncate font-bold text-black-800">
                            {workspace?.title || workspace?.workspaceName}
                        </Typography>
                    </div>
                    <IconButton size="small">
                        <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M1 1L5 5L9 1" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </IconButton>
                </div>
            }
        >
            <div className="w-[240px] py-1">
                <div className="px-4 py-2">
                    <Typography variant="caption" className="font-semibold text-black-500 uppercase">
                        {t(menuDropdown.workspaces)}
                    </Typography>
                </div>
                <div className="max-h-[300px] overflow-auto">
                    {data?.map((space: WorkspaceDto) => (
                        <ListItem
                            key={space.id}
                            onClick={() => handleChangeWorkspace(space)}
                            className={`cursor-pointer px-4 py-2 hover:bg-black-100 ${workspace?.id === space.id ? 'bg-blue-50' : ''}`}
                        >
                            <div className="flex w-full items-center justify-between">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <div
                                        className="flex h-5 w-5 min-w-[20px] items-center justify-center rounded text-[10px] font-bold text-white uppercase"
                                        style={{ backgroundColor: generateRandomBgColor(space.workspaceName) }}
                                    >
                                        {space.workspaceName.charAt(0)}
                                    </div>
                                    <Typography variant="body2" className="truncate text-black-800">
                                        {space.title || space.workspaceName}
                                    </Typography>
                                </div>
                                {workspace?.id === space.id && <Check className="h-4 w-4 text-blue-600" />}
                            </div>
                        </ListItem>
                    ))}
                </div>
                <Divider className="my-1" />
                <ListItem
                    onClick={() => openModal('CREATE_WORKSPACE')}
                    className="cursor-pointer px-4 py-2 hover:bg-black-100"
                >
                    <div className="flex items-center gap-2 text-blue-600">
                        <Plus className="h-4 w-4" />
                        <Typography variant="body2" className="font-medium">
                            {t(menuDropdown.createWorkspace)}
                        </Typography>
                    </div>
                </ListItem>
            </div>
        </MenuDropdown>
    );
}
