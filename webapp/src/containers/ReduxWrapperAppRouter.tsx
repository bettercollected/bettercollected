import { persistor, store } from '@app/store/store';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';
import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';

export default function ReduxWrapperAppRouter({ children }: any) {
    return (
        <Provider store={store}>
            <PersistGate loading={<FullScreenLoader />} persistor={persistor}>
                {children}
            </PersistGate>
        </Provider>
    );
}
