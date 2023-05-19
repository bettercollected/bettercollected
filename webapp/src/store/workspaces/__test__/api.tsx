import fetchMock, { enableFetchMocks } from 'jest-fetch-mock';

import { workspacesApi } from '@app/store/workspaces/api';
import { setupApiStore } from '@app/utils/__test_utils__/mock-rtk-store';

enableFetchMocks();

beforeEach((): void => {
    fetchMock.resetMocks();
});

describe('Test Workspace APIs', () => {
    const storeRef = setupApiStore(workspacesApi);
    test('Get Workspace Forms Success', () => {
        fetchMock.mockResponse(JSON.stringify({ data: 'Data' }));
        storeRef.store.dispatch<any>(workspacesApi.endpoints.getWorkspaceForms.initiate({ workspace_id: 'hello' })).then((action: any) => {
            expect(fetchMock).toBeCalledTimes(1);
            const { status, data, isSuccess } = action;
            expect(status).toBe('fulfilled');
            expect(isSuccess).toBe(true);
            expect(data).toStrictEqual({ data: 'Data' });
        });
    });

    test('Get Workspace Forms Failure', () => {
        fetchMock.mockReject(new Error('Internal Server Error'));
        storeRef.store.dispatch<any>(workspacesApi.endpoints.getWorkspaceForms.initiate({ workspace_id: 'hello' })).then((action: any) => {
            expect(fetchMock).toBeCalledTimes(1);
            const { status, error, isSuccess } = action;
            expect(status).toBe('rejected');
            expect(isSuccess).toBe(false);
            expect(error.error).toStrictEqual('Error: Internal Server Error');
        });
    });
});
