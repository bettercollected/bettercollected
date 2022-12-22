import { useEffect } from 'react';

import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceHOC(props: any) {
    const { workspace, children } = props;
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(setWorkspace(workspace));
    }, []);

    return <>{children}</>;
}
