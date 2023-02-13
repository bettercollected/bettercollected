import '@testing-library/jest-dom';
import { fireEvent, screen, waitFor } from '@testing-library/react';

import ProfileImageComponent from '@app/components/dashboard/profile-image';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import mockUseRouter from '@app/utils/__test_utils__/mock-use-router';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

global.URL.createObjectURL = jest.fn(() => '/favicon.ico');

mockUseRouter({}, '/abc');

describe('Banner Image Component', () => {
    it('should render component', async function () {
        renderWithProviders(<ProfileImageComponent workspace={initWorkspaceDto} isFormCreator={true} />);
        expect(screen.getByTestId('profile-image-edit')).toBeInTheDocument();
        fireEvent.change(screen.getByTestId('file-upload-profile'), {
            target: {
                files: [new File([''], 'filename', { type: 'image/png' })]
            }
        });
        expect(screen.getByTestId('profile-edit-dialog')).toBeInTheDocument();

        fireEvent.click(screen.getByTestId('save-button'));

        await waitFor(() => {
            expect(screen.queryByTestId('profile-edit-dialog')).toBe(null);
        });

        // TODO: Test updating profile image and html to canvas conversion
    });
});
