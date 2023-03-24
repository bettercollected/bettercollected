import { render } from '@testing-library/react';

import ConnectWithProviderButton from '@app/components/login/login-with-google-button';

describe('render login with google button', () => {
    it('should render login button for form responder', function () {
        render(<ConnectWithProviderButton url="url" text={'Sign in with Google'} />);
    });
    it('should render login button for form creator', function () {
        render(<ConnectWithProviderButton url="url" text={'Sign in with Google'} creator={false} />);
    });
});
