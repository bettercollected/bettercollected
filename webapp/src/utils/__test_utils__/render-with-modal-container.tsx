import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'react-redux';

import ModalContainer from '@app/components/modal-views/container';

export default function renderWithModalContainer(ui: any) {
    function Wrapper({ children }: any) {
        return <>{...children}</>;
    }

    return { ...render(ui, { wrapper: Wrapper }) };
}
