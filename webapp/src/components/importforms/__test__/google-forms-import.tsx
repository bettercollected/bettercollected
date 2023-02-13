import { fireEvent, screen, waitFor } from '@testing-library/react';

import ImportForms from '@app/components/importforms/google-forms-import';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

describe('Google Forms Import', () => {
    it('should render google forms import component', async function () {
        renderWithProviders(<ImportForms />);
        expect(screen.getByTestId('full-screen-loader')).toBeInTheDocument();
        await waitFor(() => {
            expect(screen.getByTestId('google-minified-forms')).toBeInTheDocument();
        });
        fireEvent.click(screen.getByTestId('google-minified-form1hLls0bZJBz5rE2iH6RKt7K00F3qm7b2XjsQtz55ca88'));
        screen.debug();
        await waitFor(() => {
            screen.debug();
            expect(screen.getByTestId('loader')).toBeInTheDocument();
        });

        await waitFor(() => {
            expect(screen.getByTestId('google-single-form-import')).toBeInTheDocument();
        });
    });
});
