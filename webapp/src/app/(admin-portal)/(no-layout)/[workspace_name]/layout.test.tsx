// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';

import { fakeApi, nextOutcome } from '@app/test/next-outcome';

vi.mock('next/headers', () => ({ cookies: async () => ({ get: (name: string) => (name === 'Authorization' ? { name, value: 'token' } : undefined) }) }));
vi.mock('@app/configs/environments', () => ({ default: { INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://api.internal/api/v1' } }));
vi.mock('@app/app/_dispatcher/workspace-dispatcher', () => ({ WorkspaceDispatcher: ({ children }: { children: unknown }) => children }));

const { default: Layout } = await import('./layout');

const open = (handle: string) => nextOutcome(() => Layout({ children: 'page', params: Promise.resolve({ workspace_name: handle }) }));
const workspaceLookups = (asked: string[]) => asked.filter((url) => url.includes('/workspaces?workspace_name='));

describe('the workspace dashboard layout', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('opens for a member', async () => {
        const api = fakeApi([
            ['/workspaces/mine/selection/target', 200, { next: '/acme/dashboard', notice: null }],
            ['/workspaces?workspace_name=acme', 200, { id: 'w1', workspaceName: 'acme' }]
        ]);
        vi.stubGlobal('fetch', api.fetch);
        expect((await open('acme')).value).toBeTruthy();
    });

    it('sends a non-member and a nonexistent workspace to the same notice, before reading the workspace', async () => {
        const api = fakeApi([
            ['/workspaces/mine/selection/target', 200, { next: null, notice: 'no_access' }],
            ['/workspaces?workspace_name=secret', 200, { id: 'w2', workspaceName: 'secret' }]
        ]);
        vi.stubGlobal('fetch', api.fetch);
        const notMember = await open('secret');
        const missing = await open('no-such-workspace');
        expect(notMember).toEqual({ redirect: '/workspace/select?notice=no_access' });
        expect(missing).toEqual(notMember);
        expect(workspaceLookups(api.asked)).toEqual([]);
    });

    it.each([500, 422, 504])('fails closed when the check answers %i: the selection screen, never a page or a 404', async (status) => {
        const api = fakeApi([
            ['/workspaces/mine/selection/target', status, {}],
            ['/workspaces?workspace_name=acme', 200, { id: 'w1', workspaceName: 'acme' }]
        ]);
        vi.stubGlobal('fetch', api.fetch);
        expect(await open('acme')).toEqual({ redirect: '/workspace/select' });
        expect(await open('no-such-workspace')).toEqual({ redirect: '/workspace/select' });
        expect(workspaceLookups(api.asked)).toEqual([]);
    });

    it('sends someone signed out to the sign-in page and back here', async () => {
        vi.stubGlobal('fetch', fakeApi([['/workspaces/mine/selection/target', 401, {}]]).fetch);
        expect(await open('acme')).toEqual({ redirect: '/login?redirect_to=%2Facme%2Fdashboard' });
    });
});
