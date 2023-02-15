import { fireEvent, screen } from '@testing-library/react';

import SendCode from '@app/components/login/sendcode-renderer';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

describe('render Send code ', () => {
    const updateEmail = jest.fn();
    const postSendOtp = jest.fn();

    it('should render component', function () {
        renderWithProviders(<SendCode updateEmail={updateEmail} isLoading={false} postSendOtp={postSendOtp} isCustomDomain={false} />);
        fireEvent.change(screen.getByTestId('form-input'), { target: { value: 'ankit' } });
        expect(screen.getByTestId('get-in-button')).toBeDisabled();

        fireEvent.change(screen.getByTestId('form-input'), { target: { value: 'ankit.sapkota555@gmail.com' } });

        fireEvent.click(screen.getByTestId('get-in-button'));

        expect(updateEmail).toBeCalledTimes(1);
        expect(postSendOtp).toBeCalledTimes(1);
    });
});
