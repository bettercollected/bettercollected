import { render } from '@testing-library/react';

import ConnectWithTypeForm from '@app/components/login/login-with-typeform';

describe('render login with typeform button', () => {
    it('should render login button', function () {
        render(<ConnectWithTypeForm />);
    });
});
