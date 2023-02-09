import '@testing-library/jest-dom';
import 'whatwg-fetch';

import { server } from '@app/mock/api/server';

jest.mock('@app/configs/environments', () => ({
    ENABLE_GOOGLE: true,
    ENABLE_TYPEFORM: true,
    CLIENT_HOST: 'localhost:3000',
    // api host configs
    API_ENDPOINT_HOST: 'http://localhost:8000'
}));

// Establish API mocking before all tests.
beforeAll(() => {
    server.listen();
});

beforeEach(() => {
    jest.useFakeTimers();
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
