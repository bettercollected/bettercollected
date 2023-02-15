import { render } from '@testing-library/react';

import Footer from '@app/components/landingpage/Footer';

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

jest.mock('@app/configs/environments', () => ({
    CONTACT_US_FORM_NAVIGATION_URL: '/',
    TERMS_AND_CONDITIONS: '/',
    PRIVACY_POLICY: '/'
}));

describe('renders Footer Section', () => {
    it('should render component', function () {
        render(<Footer />);
    });
});
