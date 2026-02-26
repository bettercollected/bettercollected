'use client';

import { Provider } from 'react-redux';

import { persistor, store } from '@app/store/store';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';
import { PersistGate } from 'redux-persist/integration/react';

export default function ReduxProvider({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <Provider store={store}>
            <PersistGate loading={<FullScreenLoader />} persistor={persistor}>
                {children}
            </PersistGate>
        </Provider>
    );
}
