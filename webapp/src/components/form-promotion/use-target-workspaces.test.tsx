// The workspaces a form may be copied to: each other workspace's permissions are asked for a few at a time (never all at
// once, however many workspaces there are), a workspace that does not answer is not offered, and the Idempotency-Key
// comes from a secure random source only.
import React from 'react';

import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { newIdempotencyKey } from './promotion-errors';
import { PERMISSION_CHECKS_AT_ONCE, runLimited, useTargetWorkspaces } from './use-target-workspaces';

const served = vi.hoisted(() => ({
    mine: [] as any[],
    inFlight: 0,
    peak: 0,
    calls: [] as string[],
    answer: (_id: string): Promise<any> => Promise.resolve({ data: { permissions: ['form.create'] } })
}));

// stable, like the store's own dispatch
const dispatch = (thunk: any) => (typeof thunk === 'function' ? thunk() : thunk);
vi.mock('@app/store/hooks', () => ({
    useAppDispatch: () => dispatch,
    useAppSelector: (select: any) => select({ auth: { id: 'u1' }, workspaces: { workspace: { id: 'ws-here' } } })
}));
vi.mock('@app/store/auth/slice', () => ({ selectAuth: (state: any) => state.auth }));
vi.mock('@app/store/workspaces/slice', () => ({ selectWorkspace: (state: any) => state.workspaces.workspace }));
vi.mock('@app/store/workspaces/api', () => ({
    useGetAllMineWorkspacesQuery: () => ({ data: served.mine, isLoading: false, isError: false }),
    workspacesApi: {
        endpoints: {
            getWorkspacePermissions: {
                initiate:
                    ({ workspaceId }: { workspaceId: string }) =>
                    () => {
                        served.calls.push(workspaceId);
                        served.inFlight += 1;
                        served.peak = Math.max(served.peak, served.inFlight);
                        const request: any = served.answer(workspaceId).finally(() => {
                            served.inFlight -= 1;
                        });
                        request.unsubscribe = () => {};
                        return request;
                    }
            }
        }
    }
}));

const workspaces = (count: number) => Array.from({ length: count }, (_, i) => ({ id: `ws-${i}`, title: `Voorbeeld ${i}`, workspaceName: `voorbeeld-${i}` }));

afterEach(() => {
    served.inFlight = 0;
    served.peak = 0;
    served.calls = [];
    served.answer = () => Promise.resolve({ data: { permissions: ['form.create'] } });
    vi.unstubAllGlobals();
});

describe('which workspaces are offered', () => {
    it('asks for permissions a few at a time, however many workspaces there are', async () => {
        served.mine = [{ id: 'ws-here', title: 'Hier', workspaceName: 'hier' }, ...workspaces(40)];
        served.answer = () => new Promise((resolve) => setTimeout(() => resolve({ data: { permissions: ['form.create'] } }), 5));
        const { result } = renderHook(() => useTargetWorkspaces(true));
        await waitFor(() => expect(result.current.loading).toBe(false), { timeout: 5000 });
        expect(served.calls).toHaveLength(40);
        expect(served.peak).toBeLessThanOrEqual(PERMISSION_CHECKS_AT_ONCE);
        expect(served.peak).toBeGreaterThan(1);
        // the current workspace is not a place to copy to; every other one is offered, in the list's order
        expect(result.current.workspaces.map((w) => w.id)).toEqual(workspaces(40).map((w) => w.id));
    });

    it('offers only workspaces where the person can create forms, and skips one that does not answer', async () => {
        served.mine = workspaces(4);
        served.answer = (id) => (id === 'ws-1' ? Promise.resolve({ data: { permissions: ['form.read'] } }) : id === 'ws-2' ? Promise.reject(new Error('down')) : Promise.resolve({ data: { permissions: ['form.create'] } }));
        const { result } = renderHook(() => useTargetWorkspaces(true));
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.workspaces.map((w) => w.id)).toEqual(['ws-0', 'ws-3']);
        expect(result.current.failed).toBe(false);
    });

    it('says it failed when every request failed, not that there is no workspace', async () => {
        served.mine = workspaces(3);
        served.answer = () => Promise.resolve({ error: { status: 500 } });
        const { result } = renderHook(() => useTargetWorkspaces(true));
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.failed).toBe(true);
        expect(result.current.workspaces).toEqual([]);
    });

    it('is not failed when some answered, even with none where the person can create', async () => {
        served.mine = workspaces(3);
        served.answer = (id) => (id === 'ws-0' ? Promise.resolve({ data: { permissions: ['form.read'] } }) : Promise.reject(new Error('down')));
        const { result } = renderHook(() => useTargetWorkspaces(true));
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.failed).toBe(false);
        expect(result.current.workspaces).toEqual([]);
    });

    it('starts no further request once the dialog is closed', async () => {
        served.mine = workspaces(20);
        const release: Array<() => void> = [];
        served.answer = () => new Promise((resolve) => release.push(() => resolve({ data: { permissions: ['form.create'] } })));
        const { unmount } = renderHook(() => useTargetWorkspaces(true));
        await waitFor(() => expect(served.calls).toHaveLength(PERMISSION_CHECKS_AT_ONCE));
        unmount();
        release.splice(0).forEach((resolve) => resolve());
        await new Promise((resolve) => setTimeout(resolve, 30));
        expect(served.calls).toHaveLength(PERMISSION_CHECKS_AT_ONCE);
    });

    it('asks nothing while the dialog is not open', () => {
        served.mine = workspaces(3);
        renderHook(() => useTargetWorkspaces(false));
        expect(served.calls).toEqual([]);
    });
});

describe('runLimited', () => {
    it('never runs more than the limit at once and finishes every item', async () => {
        let running = 0;
        let peak = 0;
        const done: number[] = [];
        await runLimited([...Array(25).keys()], 3, async (n) => {
            running += 1;
            peak = Math.max(peak, running);
            await new Promise((resolve) => setTimeout(resolve, 1));
            running -= 1;
            done.push(n);
        });
        expect(peak).toBe(3);
        expect(done.sort((a, b) => a - b)).toEqual([...Array(25).keys()]);
    });

    it('starts nothing more once it is told to stop', async () => {
        let stopped = false;
        const started: number[] = [];
        await runLimited(
            [...Array(10).keys()],
            2,
            async (n) => {
                started.push(n);
                stopped = true;
            },
            undefined,
            () => stopped
        );
        // the two workers that had begun before the first answer; no third item
        expect(started.length).toBeLessThanOrEqual(2);
    });

    it('is fine with nothing to do', async () => {
        await expect(runLimited([], 4, async () => {})).resolves.toBeUndefined();
    });
});

describe('the Idempotency-Key', () => {
    it('is a random UUID', () => {
        expect(newIdempotencyKey()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
        expect(newIdempotencyKey()).not.toBe(newIdempotencyKey());
    });

    it('falls back to crypto.getRandomValues, never Math.random', () => {
        const random = vi.spyOn(Math, 'random');
        vi.stubGlobal('crypto', { getRandomValues: (bytes: Uint8Array) => bytes.fill(171) });
        expect(newIdempotencyKey()).toBe('ab'.repeat(16));
        expect(random).not.toHaveBeenCalled();
        random.mockRestore();
    });

    it('refuses to make a key without a secure random source', () => {
        const random = vi.spyOn(Math, 'random');
        vi.stubGlobal('crypto', {});
        expect(() => newIdempotencyKey()).toThrow(/secure random/);
        expect(random).not.toHaveBeenCalled();
        random.mockRestore();
    });
});
