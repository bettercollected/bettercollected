import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'react-redux';

import { store as st } from '@app/store/store';

export function renderWithProviders(
    ui: any,
    {
        preloadedState: any = {},
        // Automatically create a store instance if no store was passed in
        store = st,
        ...renderOptions
    }: any = {}
) {
    function Wrapper({ children }: any) {
        return <Provider store={store}>{children}</Provider>;
    }

    return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) };
}
