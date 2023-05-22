import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'react-redux';

import ModalContainer from '@app/components/modal-views/container';
import { store as st } from '@app/store/store';

export function renderWithContainers(
    ui: any,
    {
        preloadedState: any = {},
        // Automatically create a store instance if no store was passed in
        store = st,
        ...renderOptions
    }: any = {}
) {
    function Wrapper({ children }: any) {
        return (
            <Provider store={store}>
                {children}
                <ModalContainer />
            </Provider>
        );
    }

    return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) };
}
