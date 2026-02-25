import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { isAdminDomain } from '@app/utils/domain-utils';
import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';

interface IAuthStatusDispatcherProps {
    workspace: WorkspaceDto | null | undefined;
    children: React.ReactNode | React.ReactNode[];
    isCustomDomain?: boolean;
}

export default function AuthStatusDispatcher({ workspace, children }: IAuthStatusDispatcherProps) {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const [is401, setIs401] = useState(false);

    const { data, isLoading } = useGetStatusQuery(undefined, {
        pollingInterval: 30000,
        selectFromResult: ({ data, isLoading, isError }) => {
            if (isError) setIs401(true);
            if (data) {
                const isAdmin = workspace?.ownerId === data?.id;
                return { data: { ...data, isAdmin, isLoading }, isLoading };
            }
            return { data, isLoading };
        },
        skip: is401
    });

    useEffect(() => {
        const currentPath = window.location.pathname;
        const isInvitationPage = currentPath.includes('invitation');
        const isOnAdminDomain = isAdminDomain();

        if (data) {
            const user: UserStatus = { ...data, isLoading: false };
            dispatch(setAuth(user));
        }

        if (is401) {
            dispatch(setAuth({ ...initialAuthState, isLoading: false, is401 }));

            // Only redirect if not on invitation page or admin domain
            if (!isInvitationPage && !isOnAdminDomain) {
                router.replace(window.location.href);
            }
        }

    }, [isLoading, is401, workspace]);

    return <>{children}</>;
}
