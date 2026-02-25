import { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import Tooltip from '@app/shadcn/components/ui/tooltip';
import Divider from '@Components/common/divider';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { Check } from '@app/components/icons/check';
import { Plus } from '@app/components/icons/plus';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import Loader from '@app/components/ui/loader';
import dashboardConstants from '@app/constants/locales/dashboard';
import { menuDropdown } from '@app/constants/locales/menu-dropdown';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { selectAuth, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { generateRandomBgColor } from '@app/utils/backgroundColors';
import { toEndDottedStr, trimTooltipTitle } from '@app/utils/stringUtils';
import { ChevronRight } from 'lucide-react';


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
    const isProPlan = useAppSelector(selectIsProPlan);
    const { openModal } = useFullScreenModal();
    const [open, setOpen] = useState(false);

    const { t } = useTranslation();
    const handleChangeWorkspace = (space: WorkspaceDto) => {
        if (!space?.disabled) {
            router.push(`/${space.workspaceName}/dashboard/forms`);
            setOpen(false);
        }
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
        return usersWorkspaces.length < Number(5);
    };

    const getWorkspaceRole = (space: WorkspaceDto) => {
        if (auth && space && auth?.id === space?.ownerId) return t(dashboardConstants.drawer.owner);
        return t(dashboardConstants.drawer.collaborator);
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <div
                    className={`${fullWidth ? 'w-full' : 'w-fit'} flex cursor-pointer items-center justify-between overflow-hidden rounded-lg pr-4 hover:bg-black-100 ${open ? 'bg-black-100' : ''
                        }`}
                >
                    <div className="flex w-[200px] items-center gap-2 px-3 py-1">
                        <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspace?.title || 'Untitled'} variant="circular" />
                        <div className="flex w-full flex-col items-start truncate">
                            <span className="body3 truncate">{toEndDottedStr(workspace?.title || 'Untitled', 14)}</span>
                            <p className="text-black-700 text-[12px] leading-none">{getWorkspaceRole(workspace)}</p>
                        </div>
                    </div>
                    {showExpandMore && (
                        <div className={`${open ? '!rotate-180' : '!-rotate-0'} transition-all duration-300`}>
                            <ChevronRight />
                        </div>
                    )}
                </div>
            </PopoverTrigger>
            <PopoverContent
                className="w-[320px] p-0 overflow-hidden z-[999999] bg-white"
                align="start"
                onClick={() => setOpen(false)}
                onInteractOutside={() => setOpen(false)}
            >
                <div className="max-h-[300px] overflow-auto">
                    {isLoading ? (
                        <div className="flex items-center justify-center px-5 py-3">
                            <Loader />
                        </div>
                    ) : !!data && Array.isArray(data) ? (
                        data.map((space: WorkspaceDto) => {
                            const color = generateRandomBgColor();
                            return (
                                <div
                                    key={space.id}
                                    className={`flex items-center justify-between gap-4 px-5 py-3 hover:bg-black-100 cursor-pointer ${space?.disabled && 'cursor-not-allowed'}`}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleChangeWorkspace(space);
                                    }}
                                >
                                    <div className="flex items-center gap-3">
                                        <AuthAccountProfileImage
                                            size={40}
                                            image={space?.profileImage}
                                            name={space?.title || 'Untitled'}
                                            className={color}
                                        />
                                        <div className="flex w-full flex-col items-start">
                                            <Tooltip label={trimTooltipTitle(space?.title)}>
                                                <p className="body3">{toEndDottedStr(space?.title || 'Untitled', 20)}</p>
                                            </Tooltip>
                                            <p className="text-black-700 text-[12px] leading-none">{getWorkspaceRole(space)}</p>
                                        </div>
                                    </div>
                                    {workspace.id === space.id && <Check color="#0764EB" />}
                                </div>
                            );
                        })
                    ) : (
                        <div
                            className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-black-100 cursor-pointer"
                            onClick={(e) => {
                                e.stopPropagation();
                                handleChangeWorkspace(workspace);
                            }}
                        >
                            <div className="flex items-center gap-3">
                                <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} />
                                <div className="flex w-full flex-col items-start">
                                    <Tooltip label={trimTooltipTitle(fullWorkspaceName)}>
                                        <p className="body3">{workspaceName}</p>
                                    </Tooltip>
                                    <p className="text-black-700 text-[12px] leading-none">{getWorkspaceRole(workspace)}</p>
                                </div>
                            </div>
                            <Check color="#0764EB" />
                        </div>
                    )}
                </div>
                {!isLoading && (
                    <div>
                        <Divider className="my-2" />
                        <div
                            className={`flex items-center justify-between gap-4 px-5 py-3 hover:bg-black-100 cursor-pointer ${!enableCreateWorkspaceButton() && isProPlan ? '!text-black-500 cursor-not-allowed' : '!text-black-800'
                                }`}
                            onClick={(e) => {
                                e.stopPropagation();
                                redirectToUpgradeIfNotProPlan();
                                handleCreateWorkspace();
                                setOpen(false);
                            }}
                            data-umami-event={'Create New Workspace Button'}
                            data-umami-event-email={user.email}
                        >
                            <div className="flex items-center gap-3">
                                <Plus />
                                <p className={`body3 !not-italic`}>{t(menuDropdown.createWorkspace)}</p>
                            </div>
                        </div>
                    </div>
                )}
            </PopoverContent>
        </Popover>
    );
}
