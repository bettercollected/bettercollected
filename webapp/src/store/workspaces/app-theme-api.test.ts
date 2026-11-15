import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';
import { appThemeApi } from '@app/store/workspaces/app-theme-api';
import { setWorkspace } from '@app/store/workspaces/slice';

const answer = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('choosing the app theme', () => {
    beforeEach(() => {
        store.dispatch(setWorkspace({ id: 'ws-1', title: 'Acme', appTheme: 'daybreak' }));
    });
    afterEach(() => vi.restoreAllMocks());

    it('puts the theme to the workspace\'s app-theme route, and the workspace in the store follows the answer', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(answer(200, { appTheme: 'pigment' }));
        const result: any = await store.dispatch(appThemeApi.endpoints.setWorkspaceAppTheme.initiate({ workspaceId: 'ws-1', appTheme: 'pigment' }));
        expect(result.data).toEqual({ appTheme: 'pigment' });
        const request = fetchSpy.mock.calls[0][0] as Request;
        expect(request.method).toBe('PUT');
        expect(new URL(request.url).pathname.endsWith('/workspaces/ws-1/app-theme')).toBe(true);
        expect(await request.clone().json()).toEqual({ appTheme: 'pigment' });
        expect(store.getState().workspace.appTheme).toBe('pigment');
        expect(store.getState().workspace.title).toBe('Acme');
    });

    it('leaves the workspace alone when the server refuses', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(answer(422, { code: 'app_theme_disabled', message: 'off' }));
        const result: any = await store.dispatch(appThemeApi.endpoints.setWorkspaceAppTheme.initiate({ workspaceId: 'ws-1', appTheme: 'pigment' }));
        expect(result.error.status).toBe(422);
        expect(result.error.data.code).toBe('app_theme_disabled');
        expect(store.getState().workspace.appTheme).toBe('daybreak');
    });
});
