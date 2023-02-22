/**
 * Change text changes the input fields
 * Save and assert api responses
 */
import { fireEvent, screen, waitFor } from '@testing-library/react';

import { renderWithContainers } from '@app/utils/__test_utils__/render-with-provider-and-modal-container';

import { WorkspaceDangerZoneSettings } from '../workspace-danger-zone-settings';

jest.mock('next/router', () => ({
    useRouter() {
        return {
            route: '/',
            pathname: '/dashboard/settings',
            query: {
                view: 'settings-advanced'
            },
            asPath: '',
            push: jest.fn(),
            events: {
                on: jest.fn(),
                off: jest.fn()
            },
            beforePopState: jest.fn(() => null),
            prefetch: jest.fn(() => null)
        };
    }
}));

jest.mock('@app/configs/environments', () => ({
    API_ENDPOINT_HOST: 'http://localhost:8000/api/v1'
}));

jest.mock('react-toastify', () => ({
    toast: jest.fn()
}));

// the normal function is used instead of arrow function because
// you need to use the new operator to create an InterceptionObserver object
// arrow functions cannot be used as constructors
const mockObserver: any = function () {
    return {
        observe: jest.fn(),
        disconnect: jest.fn()
    };
};

window.IntersectionObserver = mockObserver;

describe('Render workspace danger zone settings tab ', () => {
    it('renders the modal', async function () {
        renderWithContainers(<WorkspaceDangerZoneSettings />);
        const customDomainButton = screen.getByTestId('workspace-custom-domain') as HTMLButtonElement;
        fireEvent.click(customDomainButton);
        await waitFor(() => expect(screen.getByTestId('modal-view')).toBeInTheDocument());
    });
});
