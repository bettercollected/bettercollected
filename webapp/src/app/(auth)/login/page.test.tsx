// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';

import { fakeApi, nextOutcome } from '@app/test/next-outcome';

const host = vi.hoisted(() => ({ value: 'forms.example.test' }));
vi.mock('next/headers', () => ({
    cookies: async () => ({ get: (name: string) => (name === 'Authorization' ? { name, value: 'token' } : undefined) }),
    headers: async () => new Headers({ host: host.value })
}));
vi.mock('@app/configs/environments', () => ({ default: { INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://api.internal/api/v1', DASHBOARD_DOMAIN: 'admin.example.test' } }));
vi.mock('../_components/login-view', () => ({ default: () => 'login-view' }));

const { default: LoginPage } = await import('./page');

const signIn = (redirect_to?: string) => nextOutcome(() => LoginPage({ searchParams: Promise.resolve(redirect_to === undefined ? {} : { redirect_to }) }));

describe('the sign-in page, signed in', () => {
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    describe('on a form host', () => {
        it.each(['https://evil.example/', '//evil.example/x', '/\\evil.example', 'javascript:alert(1)', '/\t/evil.example'])('never follows %j', async (target) => {
            host.value = 'forms.example.test';
            vi.stubGlobal('fetch', fakeApi([['/auth/status', 200, { id: 'u1' }]]).fetch);
            vi.spyOn(console, 'error').mockImplementation(() => undefined);
            const outcome = await signIn(target);
            expect(outcome.redirect).toBeUndefined();
        });

        it('follows a path of the app', async () => {
            host.value = 'forms.example.test';
            vi.stubGlobal('fetch', fakeApi([['/auth/status', 200, { id: 'u1' }]]).fetch);
            expect(await signIn('/acme/forms/f1?lang=nl')).toEqual({ redirect: '/acme/forms/f1?lang=nl' });
        });
    });

    describe('on the dashboard host', () => {
        it('goes where the server allowed, asking only about a same-site target', async () => {
            host.value = 'admin.example.test';
            const api = fakeApi([
                ['/auth/status', 200, { id: 'u1' }],
                ['/workspaces/mine/selection', 200, { workspaces: [], isCreator: true, canCreateWorkspace: false, next: '/acme/dashboard/forms', notice: null }]
            ]);
            vi.stubGlobal('fetch', api.fetch);
            expect(await signIn('/acme/dashboard/forms')).toEqual({ redirect: '/acme/dashboard/forms' });
            expect(api.asked.some((url) => url.includes('next=%2Facme%2Fdashboard%2Fforms'))).toBe(true);
        });

        it('drops an external target before asking the server', async () => {
            host.value = 'admin.example.test';
            const api = fakeApi([
                ['/auth/status', 200, { id: 'u1' }],
                ['/workspaces/mine/selection', 200, { workspaces: [], isCreator: true, canCreateWorkspace: false, next: null, notice: null }]
            ]);
            vi.stubGlobal('fetch', api.fetch);
            expect(await signIn('https://evil.example/')).toEqual({ redirect: '/workspace/select' });
            expect(api.asked.some((url) => url.includes('evil'))).toBe(false);
        });
    });

    it('shows the sign-in form to someone signed out', async () => {
        host.value = 'admin.example.test';
        vi.stubGlobal('fetch', fakeApi([['/auth/status', 401, {}]]).fetch);
        expect((await signIn('/acme/dashboard')).value).toBeTruthy();
    });
});
