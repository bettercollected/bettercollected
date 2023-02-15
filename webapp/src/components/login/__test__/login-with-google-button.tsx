import { render } from '@testing-library/react';

import ConnectWithGoogleButton from '@app/components/login/login-with-google-button';

describe('render login with google button', () => {
    it('should render login button for form responder', function () {
        render(<ConnectWithGoogleButton text={'Sign in with google'} />);
    });

    it('should render login button for form creator', function () {
        render(<ConnectWithGoogleButton text={'Sign in with google'} creator={false} />);
    });
});
