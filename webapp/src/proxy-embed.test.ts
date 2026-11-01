import { NextRequest } from 'next/server';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearEmbedPolicyCache } from './lib/server/embed-policy';
import { proxy } from './proxy';

const env = vi.hoisted(() => ({
    DASHBOARD_DOMAIN: 'admin.example.test',
    FORM_DOMAIN: 'forms.example.test',
    HTTP_SCHEME: 'https://',
    INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://backend:8000/api/v1'
}));
vi.mock('@app/configs/environments', () => ({ default: env }));

const request = (path: string, host: string, headers: Record<string, string> = {}) => new NextRequest(`http://internal:3000${path}`, { headers: { host, ...headers } });

const policyOf = (body: unknown, ok = true) => vi.fn().mockResolvedValue({ ok, json: async () => body });
const csp = async (value: ReturnType<typeof proxy>) => (await value).headers.get('content-security-policy');

describe('proxy: who may frame a page', () => {
    beforeEach(() => {
        clearEmbedPolicyCache();
    });
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.unstubAllEnvs();
    });

    it('keeps the dashboard to itself', async () => {
        const reply = proxy(request('/acme/dashboard/forms', 'admin.example.test', { cookie: 'Authorization=x' }));
        expect(await csp(reply)).toBe("frame-ancestors 'self'");
        // the sign-in redirect carries it too
        expect(await csp(proxy(request('/acme/dashboard', 'admin.example.test')))).toBe("frame-ancestors 'self'");
    });

    it('sends no framing header on a form page while the switch is off, and asks by workspace name', async () => {
        const fetcher = policyOf({ enabled: false, origins: [] });
        vi.stubGlobal('fetch', fetcher);
        expect(await csp(proxy(request('/acme/forms/contact', 'forms.example.test')))).toBeNull();
        expect(fetcher).toHaveBeenCalledTimes(1);
        const url = new URL(fetcher.mock.calls[0][0] as string);
        expect(url.origin + url.pathname).toBe('http://backend:8000/api/v1/workspaces/embed/policy');
        expect(Object.fromEntries(url.searchParams)).toEqual({ workspace_name: 'acme' });
    });

    it('lets this site, the dashboard preview and the allowed sites frame a form page, and nobody else', async () => {
        vi.stubGlobal('fetch', policyOf({ enabled: true, origins: ['https://www.example.org', 'https://*.shop.example.org:8443'] }));
        const expected = "frame-ancestors 'self' https://admin.example.test https://www.example.org https://*.shop.example.org:8443";
        expect(await csp(proxy(request('/acme/forms/contact', 'forms.example.test')))).toBe(expected);
        expect(await csp(proxy(request('/acme/forms/contact/preview', 'forms.example.test')))).toBe(expected);
    });

    it('allows only the dashboard and itself when the workspace lists no site', async () => {
        vi.stubGlobal('fetch', policyOf({ enabled: true, origins: [] }));
        expect(await csp(proxy(request('/acme/forms/contact', 'forms.example.test')))).toBe("frame-ancestors 'self' https://admin.example.test");
    });

    it('writes nothing odd into the header, whatever the backend answered', async () => {
        vi.stubGlobal('fetch', policyOf({ enabled: true, origins: ['https://ok.example.org', 'https://x.example.org; script-src *', "https://a.example.org 'unsafe-inline'", '*', 'https://*', 'javascript:1', 'https://ok.example.org', 5, null] }));
        expect(await csp(proxy(request('/acme/forms/contact', 'forms.example.test')))).toBe("frame-ancestors 'self' https://admin.example.test https://ok.example.org");
    });

    it('refuses other sites (does not open the page) when the backend cannot be asked', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
        expect(await csp(proxy(request('/acme/forms/contact', 'forms.example.test')))).toBe("frame-ancestors 'self' https://admin.example.test");
        clearEmbedPolicyCache();
        vi.stubGlobal('fetch', policyOf({}, false));
        expect(await csp(proxy(request('/acme/forms/contact', 'forms.example.test')))).toBe("frame-ancestors 'self' https://admin.example.test");
    });

    it('keeps the answer for a short while, per workspace', async () => {
        const fetcher = policyOf({ enabled: true, origins: ['https://www.example.org'] });
        vi.stubGlobal('fetch', fetcher);
        await proxy(request('/acme/forms/a', 'forms.example.test'));
        await proxy(request('/acme/forms/b', 'forms.example.test'));
        expect(fetcher).toHaveBeenCalledTimes(1);
        await proxy(request('/other/forms/a', 'forms.example.test'));
        expect(fetcher).toHaveBeenCalledTimes(2);
    });

    it('leaves every other page alone, and the dashboard host never gets a form policy', async () => {
        const fetcher = policyOf({ enabled: true, origins: [] });
        vi.stubGlobal('fetch', fetcher);
        expect(await csp(proxy(request('/acme/forms/contact', 'admin.example.test')))).toBeNull();
        expect(await csp(proxy(request('/acme', 'forms.example.test')))).toBeNull();
        expect(await csp(proxy(request('/acme/forms', 'forms.example.test')))).toBeNull();
        expect(await csp(proxy(request('/acme/forms/contact/extra', 'forms.example.test')))).toBeNull();
        expect(fetcher).not.toHaveBeenCalled();
    });

    it('treats a malformed workspace path as an unknown workspace, not an error', async () => {
        const fetcher = policyOf({ enabled: true, origins: ['https://www.example.org'] });
        vi.stubGlobal('fetch', fetcher);
        expect(await csp(proxy(request('/%E0%A4%A/forms/contact', 'forms.example.test')))).toBe("frame-ancestors 'self' https://admin.example.test");
        expect(fetcher).not.toHaveBeenCalled();
    });

    describe('on a custom domain', () => {
        const KEYS = '1:secret-of-the-test-edge';
        const assertion = (reference: string, host: string, application = 'app_1') => {
            // eslint-disable-next-line @typescript-eslint/no-require-imports
            const { createHmac } = require('node:crypto');
            const now = Math.floor(Date.now() / 1000);
            const payload = Buffer.from(JSON.stringify({ app: application, dom: 'dom_1', ref: reference, host, iat: now, exp: now + 60, rid: 'r1' })).toString('base64url');
            const mac = createHmac('sha256', 'secret-of-the-test-edge').update(`v1.1.${payload}`).digest('base64url');
            return `v1.1.${payload}.${mac}`;
        };

        it('asks by the workspace the verified assertion names, never by a host the caller claims', async () => {
            vi.stubEnv('CUSTOM_DOMAIN_ASSERTION_KEYS', KEYS);
            vi.stubEnv('CUSTOM_DOMAIN_APPLICATION_ID', 'app_1');
            const fetcher = policyOf({ enabled: true, origins: ['https://www.example.org'] });
            vi.stubGlobal('fetch', fetcher);
            const reply = proxy(request('/forms/contact', 'forms.customer.test', { 'x-custom-domain-assertion': assertion('64b000000000000000000001', 'forms.customer.test') }));
            expect(await csp(reply)).toBe("frame-ancestors 'self' https://admin.example.test https://www.example.org");
            expect(Object.fromEntries(new URL(fetcher.mock.calls[0][0] as string).searchParams)).toEqual({ workspace_id: '64b000000000000000000001' });
        });

        it('gives a request whose assertion fails (or is for another host) the safe default and asks nobody', async () => {
            vi.stubEnv('CUSTOM_DOMAIN_ASSERTION_KEYS', KEYS);
            vi.stubEnv('CUSTOM_DOMAIN_APPLICATION_ID', 'app_1');
            const fetcher = policyOf({ enabled: true, origins: ['https://www.example.org'] });
            vi.stubGlobal('fetch', fetcher);
            for (const header of [undefined, 'v1.1.e30.bad', assertion('64b000000000000000000001', 'other.customer.test')]) {
                const reply = proxy(request('/forms/contact', 'forms.customer.test', header ? { 'x-custom-domain-assertion': header } : {}));
                expect(await csp(reply)).toBe("frame-ancestors 'self' https://admin.example.test");
            }
            expect(fetcher).not.toHaveBeenCalled();
        });

        it('asks by host only where the page itself does (no custom-domain service configured)', async () => {
            const fetcher = policyOf({ enabled: true, origins: [] });
            vi.stubGlobal('fetch', fetcher);
            await proxy(request('/forms/contact', 'forms.customer.test'));
            expect(Object.fromEntries(new URL(fetcher.mock.calls[0][0] as string).searchParams)).toEqual({ custom_domain: 'forms.customer.test' });
        });
    });
});
