import { configureStore } from '@reduxjs/toolkit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { workspacesApi } from '@app/store/workspaces/api';
import { registrationApi } from '@app/store/workspaces/registration-api';

// The real slice against a stubbed fetch: the addresses, methods and bodies
// the screens rely on. Nothing leaves the test.
const calls: Array<{ url: string; method: string; body: string }> = [];

beforeEach(() => {
    calls.length = 0;
    vi.stubGlobal(
        'fetch',
        vi.fn(async (request: Request) => {
            calls.push({ url: new URL(request.url).pathname + new URL(request.url).search, method: request.method, body: await request.text() });
            return new Response(JSON.stringify({ ok: true, items: [], total: 0 }), { status: 200, headers: { 'content-type': 'application/json' } });
        })
    );
});
afterEach(() => vi.unstubAllGlobals());

const makeStore = () => configureStore({ reducer: { [workspacesApi.reducerPath]: workspacesApi.reducer }, middleware: (getDefault) => getDefault().concat(workspacesApi.middleware) });

describe('registration API slice', () => {
    it('retries a delivery with a POST to the delivery under its own form', async () => {
        const store = makeStore();
        await store.dispatch(registrationApi.endpoints.retryRegistrationDelivery.initiate({ workspaceId: 'w1', formId: 'f1', deliveryId: 'd1' }));
        expect(calls).toHaveLength(1);
        expect(calls[0]).toMatchObject({ method: 'POST' });
        expect(calls[0].url).toMatch(/\/workspaces\/w1\/forms\/f1\/registration\/deliveries\/d1\/retry$/);
    });

    it('asks for deliveries by repeated status, with a limit and an offset', async () => {
        const store = makeStore();
        await store.dispatch(registrationApi.endpoints.getRegistrationDeliveries.initiate({ workspaceId: 'w1', formId: 'f1', status: ['failed', 'cancelled'], limit: 50 }));
        expect(calls[0].method).toBe('GET');
        expect(calls[0].url).toMatch(/registration\/deliveries\?status=failed&status=cancelled&limit=50&offset=0$/);
    });

    it('sends a service secret only in the body of the write, and tests with an empty POST', async () => {
        const store = makeStore();
        await store.dispatch(registrationApi.endpoints.createRegistrationService.initiate({ workspaceId: 'w1', body: { name: 'Cases', baseUrl: 'https://cases.example.org', auth: 'header', authName: 'X-Api-Key', secret: 'k-1' } }));
        await store.dispatch(registrationApi.endpoints.updateRegistrationService.initiate({ workspaceId: 'w1', serviceId: 's1', body: { name: 'Cases 2' } }));
        await store.dispatch(registrationApi.endpoints.testRegistrationService.initiate({ workspaceId: 'w1', serviceId: 's1' }));
        expect(calls.map((c) => `${c.method} ${c.url.split('/api/v1')[1] ?? c.url}`)).toEqual(['POST /workspaces/w1/registration/services', 'PATCH /workspaces/w1/registration/services/s1', 'POST /workspaces/w1/registration/services/s1/test']);
        expect(JSON.parse(calls[0].body)).toMatchObject({ secret: 'k-1' });
        // a patch that leaves the secret out keeps the stored one
        expect(JSON.parse(calls[1].body)).toEqual({ name: 'Cases 2' });
        expect(calls[2].body).toBe('');
        // none of the URLs carries a secret
        calls.forEach((c) => expect(c.url).not.toContain('k-1'));
    });

    it('reads the switch, and saves a form registration with PUT', async () => {
        const store = makeStore();
        await store.dispatch(registrationApi.endpoints.getRegistrationStatus.initiate('w1'));
        await store.dispatch(registrationApi.endpoints.saveFormRegistration.initiate({ workspaceId: 'w1', formId: 'f1', body: { enabled: true, serviceId: 's1', path: '/cases', variables: [{ source: 'a', key: 'postcode' }], transformToList: [] } }));
        expect(calls[0].url).toMatch(/\/workspaces\/w1\/registration\/status$/);
        expect(calls[1]).toMatchObject({ method: 'PUT' });
        expect(calls[1].url).toMatch(/\/workspaces\/w1\/forms\/f1\/registration$/);
        expect(JSON.parse(calls[1].body)).toMatchObject({ enabled: true, serviceId: 's1', path: '/cases' });
    });
});
