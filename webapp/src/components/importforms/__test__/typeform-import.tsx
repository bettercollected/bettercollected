import { fireEvent, screen, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';

import ImportTypeForms from '@app/components/importforms/typeform-import';
import { importTypeformArrayMock } from '@app/mock/data/import-google-forms-mock';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('react-toastify', () => ({
    toast: jest.fn() || {
        success: jest.fn(),
        error: jest.fn()
    }
}));

describe('Google Forms Import', () => {
    it('should render google forms import component', async function () {
        const { rerender } = renderWithProviders(<ImportTypeForms />);
        expect(screen.getByTestId('full-screen-loader')).toBeInTheDocument();
        await waitFor(() => {
            expect(screen.getByTestId('typeform-minified-form' + importTypeformArrayMock[0].id)).toBeInTheDocument();
        });
        fireEvent.click(screen.getByTestId('typeform-minified-form' + importTypeformArrayMock[0].id));
        fireEvent.click(screen.getByTestId('next-button'));
        await waitFor(() => {
            expect(screen.getByTestId('loader')).toBeInTheDocument();
        });
        await waitFor(() => {
            expect(screen.getByTestId('typeform-single-form-import')).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId('import-button'));

        await waitFor(() => {
            expect(toast).toBeCalledTimes(1);
        });
    });
});
