import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { IUserStats, initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { isAdminDomain } from '@app/utils/domainUtils';

interface IAuthStatusDispatcherProps {
    workspace: WorkspaceDto | null | undefined;
    children: React.ReactNode | React.ReactNode[];
    isCustomDomain?: boolean;
}

export default function AuthStatusDispatcher({ workspace, children, isCustomDomain = false }: IAuthStatusDispatcherProps) {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const [is401, setIs401] = useState(false);

    const { data, isLoading } = useGetStatusQuery('status', {
        pollingInterval: 10000,
        selectFromResult: ({ data, isLoading, isError }) => {
            if (isError) setIs401(true);
            if (data?.user) {
                const isAdmin = workspace?.ownerId === data?.user?.id;
                return { data: { ...data?.user, isAdmin, isLoading }, isLoading };
            }
            return { data, isLoading };
        },
        skip: is401
    });

    useEffect(() => {
        if (data) {
            const user: IUserStats = { ...data, isLoading: false };
            dispatch(setAuth(user));
        }
        if (is401) {
            dispatch(setAuth({ ...initialAuthState, isLoading: false }));
            if (isAdminDomain()) router.replace(router.asPath);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isLoading, is401, workspace]);

    return <>{children}</>;
}
