import { configureStore } from '@reduxjs/toolkit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { pathSegment, workspacesApi } from '@app/store/workspaces/api';

// The real slice against a stubbed fetch: the addresses a response's page asks.
// A response id comes from the page's URL, so it must stay one path segment.
const calls: Array<{ url: string; method: string }> = [];

beforeEach(() => {
    calls.length = 0;
    vi.stubGlobal(
        'fetch',
        vi.fn(async (request: Request) => {
            calls.push({ url: request.url, method: request.method });
            return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } });
        })
    );
});
afterEach(() => vi.unstubAllGlobals());

const makeStore = () => configureStore({ reducer: { [workspacesApi.reducerPath]: workspacesApi.reducer }, middleware: (getDefault) => getDefault().concat(workspacesApi.middleware) });
const path = (url: string) => new URL(url, 'http://localhost').pathname;

describe('response ids in API paths', () => {
    it('keeps an id one segment: slashes, queries and dot segments cannot climb or change the path', () => {
        expect(pathSegment('r1')).toBe('r1');
        expect(pathSegment('../../admin')).toBe('..%2F..%2Fadmin');
        expect(pathSegment('a?b#c')).toBe('a%3Fb%23c');
        expect(pathSegment('..')).toBe('%252E%252E');
        expect(pathSegment('.')).toBe('%252E');
    });

    it('asks for one submission under its workspace, whatever the route id holds', async () => {
        const store = makeStore();
        await store.dispatch(workspacesApi.endpoints.getWorkspaceSubmission.initiate({ workspace_id: 'w1', submission_id: '../../forms' }));
        await store.dispatch(workspacesApi.endpoints.getWorkspaceSubmission.initiate({ workspace_id: 'w1', submission_id: '..' }));
        expect(calls.map((call) => path(call.url).split('/api/v1')[1] ?? path(call.url))).toEqual(['/workspaces/w1/submissions/..%2F..%2Fforms', '/workspaces/w1/submissions/%252E%252E']);
    });

    it('deletes one response under its form', async () => {
        const store = makeStore();
        await store.dispatch(workspacesApi.endpoints.deleteResponse.initiate({ workspaceId: 'w1', formId: 'f1', responseId: 'r1/../../x' }));
        expect(calls[0].method).toBe('DELETE');
        expect(path(calls[0].url)).toMatch(/\/workspaces\/w1\/forms\/f1\/response\/r1%2F..%2F..%2Fx$/);
    });
});
