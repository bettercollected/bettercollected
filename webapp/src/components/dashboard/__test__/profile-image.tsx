import '@testing-library/jest-dom';
import { fireEvent, screen } from '@testing-library/react';

import ProfileImageComponent from '@app/components/dashboard/profile-image';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import mockUseRouter from '@app/utils/__test_utils__/mock-use-router';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

global.URL.createObjectURL = jest.fn(() => '/favicon.ico');

mockUseRouter({}, '/abc');

describe('Profile Image Component', () => {
    it('should render component', async function () {
        renderWithProviders(<ProfileImageComponent workspace={initWorkspaceDto} isFormCreator={true} />);
        expect(screen.getByTestId('profile-image-edit')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('profile-image-edit'));
        expect(screen.getByTestId('profile-edit-dialog')).toBeInTheDocument();

        // TODO: Test updating profile image and html to canvas conversion
    });
});
