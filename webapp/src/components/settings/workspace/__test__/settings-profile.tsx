/**
 * Change text changes the input fields
 * Save and assert api responses
 */
import { useRouter } from 'next/router';

import { fireEvent, getByText, render, screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { toast } from 'react-toastify';

import { ToastId } from '@app/constants/toastId';
import { server } from '@app/mock/api/server';
import { workspaceMock } from '@app/mock/data/workspace-mock';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

import SettingsProfile from '../settings-profile';

jest.mock('@app/configs/environments', () => ({
    API_ENDPOINT_HOST: 'http://localhost:8000/api/v1'
}));

jest.mock('react-toastify', () => ({
    toast: jest.fn()
}));

describe('Render settings profile tab ', () => {
    it('assert the presence of the elements in settings profile tab', async function () {
        const { getByText } = renderWithProviders(<SettingsProfile />);
        expect(getByText('Workspace Information')).toBeInTheDocument();
        expect(getByText('Workspace Description')).toBeInTheDocument();
    });

    it('updates the change in text input for workspace title and triggers endpoint ', async function () {
        server.use(
            rest.patch('http://localhost:8000/api/v1/workspaces/:workspace_id', (req, res, ctx) => {
                return res(ctx.body(JSON.stringify(workspaceMock)));
            })
        );
        renderWithProviders(<SettingsProfile />);
        const workspaceTitle = 'Test workspace';
        // const workspaceTitleInput = screen.getByRole('textbox', { name: /workspace-title/i }) as HTMLInputElement;
        const workspaceTitleInput = screen.getByTestId('workspace-title').querySelector('input') as HTMLInputElement;

        fireEvent.change(workspaceTitleInput, { target: { value: workspaceTitle } });
        expect(workspaceTitleInput).toHaveValue(workspaceTitle);
        const updateWorkspaceButton = screen.getByRole('button', {
            name: /Update workspace profile/i
        });
        fireEvent.click(updateWorkspaceButton);
        await waitFor(() => {
            expect(toast).toBeCalledWith('Workspace Updated!!!', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        });
    });

    it('checks if the change input reflects on renders ', async function () {
        server.use(
            rest.patch('http://localhost:8000/api/v1/workspaces/:workspace_id', (req, res, ctx) => {
                return res(ctx.body(JSON.stringify(workspaceMock)));
            })
        );
        renderWithProviders(<SettingsProfile />);
        const workspaceTitle = 'Test workspace';

        // test for workspace title
        // const workspaceTitleInput = screen.getByRole('textbox', { name: /workspace-title/i }) as HTMLInputElement;
        const workspaceTitleInput = screen.getByTestId('workspace-title').querySelector('input') as HTMLInputElement;
        fireEvent.change(workspaceTitleInput, { target: { value: workspaceTitle } });
        expect(workspaceTitleInput).toHaveValue(workspaceTitle);

        // test for workspace description
        const workspaceDescriptionInput = screen.getByPlaceholderText('Enter about your workspace');
        fireEvent.change(workspaceDescriptionInput, { target: { value: workspaceTitle } });
        expect(workspaceDescriptionInput).toHaveValue(workspaceTitle);

        // test for workspace profile image
        const workspaceBannerInput = screen.getByTestId('workspace-banner');
        const file = new File(['(⌐□_□)'], 'test.png', { type: 'image/png' });
        global.URL.createObjectURL = jest.fn(() => 'https://1.com');
        await waitFor(() => {
            fireEvent.change(workspaceBannerInput, {
                target: { files: [file] }
            });
        });
        const bannerImageDiv = screen.getByTestId('banner-image-display') as HTMLImageElement;
        expect(bannerImageDiv.src).toContain('http://localhost/_next/image?url=https%3A%2F%2F1.com&w=3840&q=75');
    });
});
