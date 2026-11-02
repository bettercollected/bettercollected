// Editing an API key refreshes the list of keys and nothing else: the single sign-on page lists the keys that predate
// its requirement, and an edit (name, role, forms) never changes which keys those are, so it must not be asked again.
import { afterEach, describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';

const calls: Array<{ method: string; url: string }> = [];

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });

const asked = (method: string, part: string) => calls.filter((call) => call.method === method && call.url.includes(part)).length;
const settle = () => new Promise((resolve) => setTimeout(resolve, 50));

afterEach(() => {
    vi.unstubAllGlobals();
    calls.length = 0;
});

describe('the tags an API key edit invalidates', () => {
    it('refreshes the keys, not the single sign-on page', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async (request: Request) => {
                calls.push({ method: request.method, url: request.url });
                return json([]);
            })
        );
        const keys = store.dispatch(workspacesApi.endpoints.getAPIKeys.initiate('ws-1'));
        const sso = store.dispatch(workspacesApi.endpoints.getWorkspaceSso.initiate('ws-1'));
        await keys;
        await sso;
        expect([asked('GET', '/api-keys'), asked('GET', '/sso')]).toEqual([1, 1]);

        await store.dispatch(workspacesApi.endpoints.updateAPIKey.initiate({ workspace_id: 'ws-1', key_id: 'k1', body: { name: 'Renamed' } }));
        await settle();

        expect(asked('PATCH', '/api-keys/k1')).toBe(1);
        expect(asked('GET', '/api-keys')).toBe(2);
        expect(asked('GET', '/sso')).toBe(1);
        keys.unsubscribe();
        sso.unsubscribe();
    });

    it('still refreshes the single sign-on page when a key is revoked', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async (request: Request) => {
                calls.push({ method: request.method, url: request.url });
                return json([]);
            })
        );
        const sso = store.dispatch(workspacesApi.endpoints.getWorkspaceSso.initiate('ws-2'));
        await sso;
        await store.dispatch(workspacesApi.endpoints.revokeAPIKey.initiate({ workspace_id: 'ws-2', key_id: 'k1' }));
        await settle();
        expect(asked('GET', '/sso')).toBe(2);
        sso.unsubscribe();
    });
});
