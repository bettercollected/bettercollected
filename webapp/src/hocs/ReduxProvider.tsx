'use client';

import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';

import { persistor, store } from '@app/store/store';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

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
