'use client';

import AuthStatusDispatcher from '@Components/HOCs/AuthStatusDispatcher';
import ServerSideWorkspaceDispatcher from '@Components/HOCs/ServerSideWorkspaceDispatcher';
import useWorkspace from '@app/store/jotai/workspace';
import { persistor, store } from '@app/store/store';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';
import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';

export default function ReduxWrapperAppRouter({ children }: any) {
    const { workspace } = useWorkspace();
    return (
        <Provider store={store}>
            <PersistGate loading={<FullScreenLoader />} persistor={persistor}>
                <ServerSideWorkspaceDispatcher workspace={workspace}>
                    <AuthStatusDispatcher workspace={workspace}>{children}</AuthStatusDispatcher>
                </ServerSideWorkspaceDispatcher>
            </PersistGate>
        </Provider>
    );
}
