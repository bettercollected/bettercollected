import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import UpdateWorkspaceSettings from '@app/components/workspace/update-workspace-settings';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('@app/components/modal-views/context', () => ({
    useModal: jest.fn()
}));
jest.mock('next/router', () => ({
    useRouter() {
        return {
            route: '/',
            pathname: '/',
            query: null,
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

jest.mock('react-toastify', () => ({
    toast: {
        error: jest.fn(),
        info: jest.fn()
    }
}));

describe('Update Workspace Settings', () => {
    it('should render the component', async function () {
        const mockModal = {
            closeModal: jest.fn()
        };
        (useModal as jest.Mock).mockReturnValue(mockModal);

        renderWithProviders(<UpdateWorkspaceSettings updateDomain={true} />);
        act(() => {
            fireEvent.change(screen.getByTestId('update-field'), {
                target: {
                    value: 'google'
                }
            });
        });
        // expect(screen.getByTestId('save-button')).toBeDisabled();
        act(() => {
            fireEvent.change(screen.getByTestId('update-field'), {
                target: {
                    value: 'google.com'
                }
            });
        });

        fireEvent.click(screen.getByTestId('save-button'));

        await waitFor(() => {
            expect(toast.info).toBeCalledTimes(1);
        });
    });
});
