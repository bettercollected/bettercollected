import '@testing-library/jest-dom';
import fetchMock, { enableFetchMocks } from 'jest-fetch-mock';

import mockUseRouter from '@app/utils/__test_utils__/mock-use-router';

enableFetchMocks();

beforeEach((): void => {
    fetchMock.resetMocks();
});

global.URL.createObjectURL = jest.fn(() => '/favicon.ico');

mockUseRouter({ sub_id: '123456' }, '/ankit/dashboard');

const imgFile = new File(['(⌐□_□)'], 'bettercollected.png', { type: 'image/png' });

jest.mock('html2canvas', () => ({
    html2canvas: () => {
        return Promise.resolve(() => ({
            toBlob: () => {
                return Promise.resolve(() => {
                    return imgFile;
                });
            }
        }));
    }
}));

describe('Banner Image Component', () => {
    it('should render component', async function () {
        fetchMock.mockResponse(JSON.stringify('Hello Wrold'));
        // renderWithProviders(<BannerImageComponent workspace={initWorkspaceDto} isFormCreator={true} />);
        // expect(screen.getByText('update image')).toBeInTheDocument();
    });
});
