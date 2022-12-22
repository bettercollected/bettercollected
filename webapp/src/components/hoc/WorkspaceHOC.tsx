import { useEffect } from 'react';

import { useRouter } from 'next/router';

import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceHOC(props: any) {
    const { workspace, children } = props;
    const dispatch = useAppDispatch();
    const router = useRouter();

    useEffect(() => {
        dispatch(setWorkspace(workspace));
    }, [router.asPath]);

    return <>{children}</>;
}
