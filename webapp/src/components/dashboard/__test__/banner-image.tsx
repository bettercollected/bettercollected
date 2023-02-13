import '@testing-library/jest-dom';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import fetchMock, { enableFetchMocks } from 'jest-fetch-mock';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import mockUseRouter from '@app/utils/__test_utils__/mock-use-router';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

enableFetchMocks();

beforeEach((): void => {
    fetchMock.resetMocks();
});

global.URL.createObjectURL = jest.fn(() => '/favicon.ico');

mockUseRouter({ sub_id: '123456' }, '/ankit/dashboard');

describe('Banner Image Component', () => {
    it('should render component', async function () {
        fetchMock.mockResponse(JSON.stringify('Hello Wrold'));
        renderWithProviders(<BannerImageComponent workspace={initWorkspaceDto} isFormCreator={true} />);
        expect(screen.getByText('update image')).toBeInTheDocument();
        fireEvent.change(screen.getByTestId('file-upload'), {
            target: {
                files: [new File([''], 'filename', { type: 'image/png' })]
            }
        });

        await waitFor(() => {});

        // TODO: Test updating banner image and html to canvas conversion
    });
});
