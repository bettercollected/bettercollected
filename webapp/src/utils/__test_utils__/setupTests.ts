import '@testing-library/jest-dom';
import 'whatwg-fetch';

import { server } from '@app/mock/api/server';
import mockUseRouter from '@app/utils/__test_utils__/mock-use-router';


jest.mock('@app/configs/environments', () => ({
    ENABLE_GOOGLE: true,
    ENABLE_TYPEFORM: true,
    CLIENT_DOMAIN: 'localhost:3000',
    // api host configs
    API_ENDPOINT_HOST: 'http://localhost:8000'
}));

// Establish API mocking before all tests.
beforeAll(() => {
    server.listen();
});

beforeEach(() => {
    jest.useFakeTimers();
    mockUseRouter();
});
// Reset any request handlers that we may add during the tests,
// so they don't affect other tests.
afterEach(() => {
    server.resetHandlers();
    // This is the solution to clear RTK Query cache after each test
    // store.dispatch(workspacesApi.util.resetApiState());
});

// Clean up after the tests are finished.
afterAll(() => server.close());