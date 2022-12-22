import { useEffect } from 'react';

import { setWorkspace } from '@app/store/counter/workspaceSlice';
import { useAppDispatch } from '@app/store/hooks';

export default function WorkspaceHOC(props: any) {
    const { workspace, children } = props;
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(setWorkspace(workspace));
    }, []);

    return <>{children}</>;
}
