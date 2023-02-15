import { fireEvent, screen, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';

import ImportForms from '@app/components/importforms/google-forms-import';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('react-toastify', () => ({
    toast: {
        success: jest.fn(),
        error: jest.fn()
    }
}));

describe('Google Forms Import', () => {
    it('should render google forms import component', async function () {
        const { rerender } = renderWithProviders(<ImportForms />);
        expect(screen.getByTestId('full-screen-loader')).toBeInTheDocument();
        await waitFor(() => {
            expect(screen.getByTestId('google-minified-forms')).toBeInTheDocument();
        });
        fireEvent.click(screen.getByTestId('google-minified-form1hLls0bZJBz5rE2iH6RKt7K00F3qm7b2XjsQtz55ca88'));
        fireEvent.click(screen.getByTestId('next-button'));
        await waitFor(() => {
            expect(screen.getByTestId('loader')).toBeInTheDocument();
        });
        await waitFor(() => {
            expect(screen.getByTestId('google-single-form-import')).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId('import-button'));

        await waitFor(() => {
            expect(toast.success).toBeCalledTimes(1);
        });
    });
});
