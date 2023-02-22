import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'react-redux';

import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { store as st } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

export function renderWithProviders(
    ui: any,
    {
        preloadedState: any = {},
        // Automatically create a store instance if no store was passed in
        store = st,
        ...renderOptions
    }: any = {}
) {
    st.dispatch(setWorkspace(initWorkspaceDto));
    function Wrapper({ children }: any) {
        return <Provider store={store}>{children}</Provider>;
    }

    return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) };
}
