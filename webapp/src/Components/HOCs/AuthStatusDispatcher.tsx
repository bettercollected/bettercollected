import React, { useEffect, useState } from 'react';

import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { IUserStats, initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';

interface IAuthStatusDispatcherProps {
    workspace: WorkspaceDto | null | undefined;
    children: React.ReactNode | React.ReactNode[];
}

export default function AuthStatusDispatcher({ workspace, children }: IAuthStatusDispatcherProps) {
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
        if (workspace && data) {
            const user: IUserStats = { ...data, isLoading: false };
            dispatch(setAuth(user));
        }
        if (is401) dispatch(setAuth({ ...initialAuthState, isLoading: false }));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isLoading, is401, workspace]);

    return <>{children}</>;
}
