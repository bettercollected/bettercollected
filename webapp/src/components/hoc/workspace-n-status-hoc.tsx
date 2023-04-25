import { useEffect } from 'react';

import { useRouter } from 'next/router';

import { useGetStatusQuery } from '@app/store/auth/api';
import { setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceNStatusHoc(props: any) {
    const { workspace, children } = props;
    const dispatch = useAppDispatch();
    const router = useRouter();

    const { data, error } = useGetStatusQuery('status', { pollingInterval: 10000 });

    useEffect(() => {
        dispatch(setWorkspace(workspace));
    }, []);

    useEffect(() => {
        if (data) {
            const user = { ...data?.user };
            user.isAdmin = workspace?.ownerId === user.id;
            dispatch(setAuth(user));
        }
        if (error) {
            router.push('/login');
        }
    }, [data]);

    return <>{children}</>;
}
