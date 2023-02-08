import { fireEvent, render, screen } from '@testing-library/react';

import ImportFormsMenu from '@app/components/dashboard/import-forms-menu';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('@app/configs/environments', () => ({
    ENABLE_GOOGLE: true,
    ENABLE_TYPEFORM: true
}));

jest.mock('next/router', () => ({
    useRouter() {
        return {
            route: '/',
            pathname: '',
            query: '',
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

describe('Render Import Menu When button is clicked', () => {
    it('should render button', function () {
        render(<ImportFormsMenu />);
        fireEvent.click(screen.getByText('Import Forms'));
        expect(screen.getByTestId('google-menu-item')).toBeInTheDocument();
        expect(screen.getByTestId('typeform-menu-item')).toBeInTheDocument();
    });

    // TODO: check if correct model is opened when clicking a particular item
});
