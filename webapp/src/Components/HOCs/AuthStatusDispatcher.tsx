import React, { useEffect, useState } from 'react';

import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetStatusQuery } from '@app/store/auth/api';
import { IUserStats, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';

interface IAuthStatusDispatcherProps {
    workspace: WorkspaceDto | null | undefined;
    children: React.ReactNode | React.ReactNode[];
}

export default function AuthStatusDispatcher({ workspace, children }: IAuthStatusDispatcherProps) {
    const dispatch = useAppDispatch();
    const [is401, setIs401] = useState(false);

    const { data } = useGetStatusQuery('status', {
        pollingInterval: 10000,
        selectFromResult: ({ data, isError }) => {
            if (isError) setIs401(true);
            return { data };
        },
        skip: is401
    });

    useEffect(() => {
        if (workspace && !!data) {
            const user: IUserStats = { ...data?.user };
            if (!!user) {
                user.isAdmin = workspace?.ownerId === user.id;
                dispatch(setAuth(user));
            }
        }
    }, []);

    return <>{children}</>;
}
