import { configureStore } from '@reduxjs/toolkit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { workspacesApi } from '@app/store/workspaces/api';
import { formAccessApi } from '@app/store/workspaces/form-access-api';

// The real slice against a stubbed fetch: the two read-only routes the Access screens added (the picker and the
// dry run of restricting a form), and the shape of what they bring back.
const calls: Array<{ url: string; method: string }> = [];

beforeEach(() => {
    calls.length = 0;
    vi.stubGlobal(
        'fetch',
        vi.fn(async (request: Request) => {
            calls.push({ url: request.url, method: request.method });
            const body = request.url.includes('/access/impact') ? { mode: 'restricted', membersLosingAccess: 4 } : { members: [{ id: 'u1', name: 'Cor Jansen' }], teams: [{ id: 't1', name: 'Redactie', memberCount: 2 }] };
            return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } });
        })
    );
});
afterEach(() => vi.unstubAllGlobals());

const makeStore = () => configureStore({ reducer: { [workspacesApi.reducerPath]: workspacesApi.reducer }, middleware: (getDefault) => getDefault().concat(workspacesApi.middleware) });
const tail = (url: string) => {
    const parsed = new URL(url, 'http://localhost');
    return `${parsed.pathname.split('/api/v1')[1] ?? parsed.pathname}${parsed.search}`;
};

describe('form access: the picker and the dry run', () => {
    it('reads the candidates of one form under its workspace, with a GET and no body', async () => {
        const result = await makeStore().dispatch(formAccessApi.endpoints.getFormAccessCandidates.initiate({ workspaceId: 'w1', formId: 'f1' }));
        expect(calls).toHaveLength(1);
        expect(calls[0].method).toBe('GET');
        expect(tail(calls[0].url)).toBe('/workspaces/w1/forms/f1/access/candidates');
        expect(result.data).toEqual({ members: [{ id: 'u1', name: 'Cor Jansen' }], teams: [{ id: 't1', name: 'Redactie', memberCount: 2 }] });
    });

    it('asks for the dry run of restricting with the mode in the query, and changes nothing (GET)', async () => {
        const result = await makeStore().dispatch(formAccessApi.endpoints.getFormAccessImpact.initiate({ workspaceId: 'w1', formId: 'f1', mode: 'restricted' }));
        expect(calls).toHaveLength(1);
        expect(calls[0].method).toBe('GET');
        expect(tail(calls[0].url)).toBe('/workspaces/w1/forms/f1/access/impact?mode=restricted');
        expect(result.data?.membersLosingAccess).toBe(4);
    });

    it('keeps an id one path segment, whatever the page holds', async () => {
        await makeStore().dispatch(formAccessApi.endpoints.getFormAccessCandidates.initiate({ workspaceId: 'w1', formId: '../../x' }));
        expect(tail(calls[0].url)).toBe('/workspaces/w1/forms/..%2F..%2Fx/access/candidates');
    });
});
