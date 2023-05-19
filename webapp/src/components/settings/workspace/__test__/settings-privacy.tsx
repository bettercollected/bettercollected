import { useRouter } from 'next/router';

import { fireEvent, screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';

import { server } from '@app/mock/api/server';
import { workspaceMock } from '@app/mock/data/workspace-mock';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

import Settingsprivacy from '../settings-privacy';

jest.mock('next/router', () => ({
    useRouter: jest.fn()
}));

jest.mock('@app/configs/environments', () => ({
    API_ENDPOINT_HOST: 'http://localhost:8000/api/v1'
}));

describe('Render settings privacy tab ', () => {
    afterEach(() => {
        // Reset any runtime handlers tests may use.
        server.resetHandlers();
    });

    afterAll(() => {
        // Clean up once the tests are done.
        server.close();
    });

    it('update the input change of the url ', async function () {
        renderWithProviders(<Settingsprivacy />);
        const testPrivacyPolicyUrl = 'http://www.hello.com';
        const privacyInput = screen.getByTestId('privacy-policy').querySelector('input') as HTMLInputElement;
        expect(privacyInput as HTMLInputElement).toBeInTheDocument();
        fireEvent.change(privacyInput, { target: { value: testPrivacyPolicyUrl } });
        expect(privacyInput.value).toEqual(testPrivacyPolicyUrl);
        const termsOfServiceInput = screen.getByTestId('terms-of-service').querySelector('input') as HTMLInputElement;
        expect(termsOfServiceInput).toBeInTheDocument();
        fireEvent.change(termsOfServiceInput, { target: { value: testPrivacyPolicyUrl } });
        expect(termsOfServiceInput.value).toEqual(testPrivacyPolicyUrl);
    });

    it('checks the validity of url for privacy policy text input', async function () {
        renderWithProviders(<Settingsprivacy />);
        // const privacyInput = screen.getByRole('textbox', { name: /privacy-policy/i }) as HTMLInputElement;
        const privacyInput = screen.getByTestId('privacy-policy').querySelector('input') as HTMLInputElement;

        // when a url format is proper, the aria-invalid is false
        const correctPrivacyPolicyUrl = 'https://b.com';
        fireEvent.change(privacyInput, { target: { value: correctPrivacyPolicyUrl } });
        await waitFor(() => expect(privacyInput).toBeValid());

        // when a url format is invalid, aria-invalid attribute is true
        const incorrectPrivacyPolicyUrl = 'b';
        fireEvent.change(privacyInput, { target: { value: incorrectPrivacyPolicyUrl } });
        await waitFor(() => expect(privacyInput).not.toBeValid());
    });

    it('checks the validity of url for terms of service text input', async function () {
        // when a url format is proper, the aria-invalid is false
        renderWithProviders(<Settingsprivacy />);
        // const termsofServiceInput = screen.getByRole('textbox', { name: /terms-of-service/i }) as HTMLInputElement;
        const termsofServiceInput = screen.getByTestId('terms-of-service').querySelector('input') as HTMLInputElement;

        const correctTermsOfServiceUrl = 'https://b.com';
        fireEvent.change(termsofServiceInput, { target: { value: correctTermsOfServiceUrl } });
        await waitFor(() => expect(termsofServiceInput).toBeValid());

        const incorrectTermsOfServiceUrl = 'b';
        fireEvent.change(termsofServiceInput, { target: { value: incorrectTermsOfServiceUrl } });
        await waitFor(() => expect(termsofServiceInput).not.toBeValid());
    });

    it('returns mock response from api when valid url is passed', async function () {
        const mockRouter = {
            push: jest.fn()
        };
        (useRouter as jest.Mock).mockReturnValue(mockRouter);
        server.use(
            rest.patch('http://localhost:8000/api/v1/workspaces/:workspace_id/policies', (req, res, ctx) => {
                return res(ctx.body(JSON.stringify(workspaceMock)));
            })
        );
        renderWithProviders(<Settingsprivacy />);
        // const privacyInput = screen.getByRole('textbox', { name: /privacy-policy/i }) as HTMLInputElement;
        const privacyInput = screen.getByTestId('privacy-policy').querySelector('input') as HTMLInputElement;

        const editButton = screen.getByTestId('privacy-policy-edit-button');
        fireEvent.click(editButton);
        const correctPrivacyPolicyUrl = 'https://better.com';
        fireEvent.change(privacyInput, { target: { value: correctPrivacyPolicyUrl } });
        await waitFor(() => expect(privacyInput).toBeValid());
        const saveButton = screen.getByTestId('privacy-policy-save-button');
        fireEvent.click(saveButton);
        await waitFor(() => {
            expect(screen.getByTestId('privacy-policy-edit-button')).toBeInTheDocument();
            expect(mockRouter.push).toBeCalledTimes(1);
        });
    });
});
