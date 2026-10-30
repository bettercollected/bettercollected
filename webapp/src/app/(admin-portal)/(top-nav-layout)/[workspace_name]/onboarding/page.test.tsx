// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';

import { fakeApi, nextOutcome } from '@app/test/next-outcome';

vi.mock('next/headers', () => ({
    cookies: async () => ({ get: (name: string) => (name === 'Authorization' ? { name, value: 'token' } : undefined) }),
    headers: async () => new Headers({ host: 'admin.example.test' })
}));
vi.mock('@app/configs/environments', () => ({ default: { INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://api.internal/api/v1', DASHBOARD_DOMAIN: 'admin.example.test', FORM_DOMAIN: 'forms.example.test' } }));
vi.mock('./_components/onbaording-client', () => ({ default: () => 'onboarding' }));

const { default: OnboardingPage } = await import('./page');

const open = (handle: string) => nextOutcome(() => OnboardingPage({ params: Promise.resolve({ workspace_name: handle }) }));
const workspaceLookups = (asked: string[]) => asked.filter((url) => url.includes('/workspaces?workspace_name='));

describe('the onboarding page', () => {
    afterEach(() => vi.unstubAllGlobals());

    it("never shows someone else's untitled workspace: a non-member and a nonexistent handle get the same notice", async () => {
        const api = fakeApi([
            ['/workspaces/mine/selection/target', 200, { next: null, notice: 'no_access' }],
            ['/workspaces?workspace_name=', 200, { id: 'w2', workspaceName: 'theirs', title: '' }]
        ]);
        vi.stubGlobal('fetch', api.fetch);
        const notMember = await open('theirs');
        const missing = await open('no-such-workspace');
        expect(notMember).toEqual({ redirect: '/workspace/select?notice=no_access' });
        expect(missing).toEqual(notMember);
        expect(workspaceLookups(api.asked)).toEqual([]);
    });

    it('fails closed when the check has no answer', async () => {
        vi.stubGlobal('fetch', fakeApi([['/workspaces/mine/selection/target', 500, {}]]).fetch);
        expect(await open('mine')).toEqual({ redirect: '/workspace/select' });
    });

    it("onboards a member's untitled workspace", async () => {
        vi.stubGlobal(
            'fetch',
            fakeApi([
                ['/workspaces/mine/selection/target', 200, { next: '/mine/dashboard', notice: null }],
                ['/workspaces?workspace_name=mine', 200, { id: 'w1', workspaceName: 'mine', title: 'Untitled' }]
            ]).fetch
        );
        expect((await open('mine')).value).toBeTruthy();
    });

    it("sends a member's titled workspace to its dashboard", async () => {
        vi.stubGlobal(
            'fetch',
            fakeApi([
                ['/workspaces/mine/selection/target', 200, { next: '/acme/dashboard', notice: null }],
                ['/workspaces?workspace_name=acme', 200, { id: 'w1', workspaceName: 'acme', title: 'Acme' }]
            ]).fetch
        );
        expect(await open('acme')).toEqual({ redirect: '/acme/dashboard' });
    });

    it('sends someone signed out to the sign-in page', async () => {
        vi.stubGlobal('fetch', fakeApi([['/workspaces/mine/selection/target', 401, {}]]).fetch);
        expect((await open('acme')).redirect).toMatch(/^\/login\?redirect_to=/);
    });
});
