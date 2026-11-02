import { NextRequest } from 'next/server';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { frameAncestorsFor } from './lib/frame-ancestors';
import { clearEmbedPolicyCache } from './lib/server/embed-policy';
import { config, proxy } from './proxy';

const env = vi.hoisted(() => ({ DASHBOARD_DOMAIN: 'admin.example.test', FORM_DOMAIN: 'forms.example.test', HTTP_SCHEME: 'https://', INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://backend:8000/api/v1' }));
vi.mock('@app/configs/environments', () => ({ default: env }));

const SELF_AND_DASHBOARD = "frame-ancestors 'self' https://admin.example.test";

const request = (path: string, host: string, cookie = 'Authorization=x') => new NextRequest(`http://internal:3000${path}`, { headers: { host, cookie } });
// the embed switch is off on the stand-in backend: a published form's page then carries no header, as before
const fetcher = vi.fn();
const answer = async (path: string, host: string, cookie?: string) => proxy(request(path, host, cookie));
const csp = async (path: string, host = 'admin.example.test') => (await answer(path, host)).headers.get('content-security-policy');

describe('which pages may be framed by whom', () => {
    beforeEach(() => {
        clearEmbedPolicyCache();
        fetcher.mockReset();
        fetcher.mockResolvedValue({ ok: true, json: async () => ({ enabled: false, origins: [] }) });
        vi.stubGlobal('fetch', fetcher);
    });
    afterEach(() => {
        vi.unstubAllGlobals();
        env.DASHBOARD_DOMAIN = 'admin.example.test';
        env.HTTP_SCHEME = 'https://';
    });

    it.each([
        ['the dashboard', '/acme/dashboard', 'admin.example.test'],
        ['a dashboard page', '/acme/dashboard/forms', 'admin.example.test'],
        ['an admin portal page (form editor)', '/acme/dashboard/forms/6ae4ea8517e776a22c1a5b01', 'admin.example.test'],
        ['an admin portal page (responses)', '/acme/dashboard/forms/6ae4ea8517e776a22c1a5b01/responses', 'admin.example.test'],
        ['the settings pages', '/acme/dashboard/embedding', 'admin.example.test'],
        ['the sign-in page', '/login', 'admin.example.test'],
        ['the root', '/', 'admin.example.test'],
        ['a receipt', '/submissions/uuid/6ae4ea8517e776a22c1a5b09', 'forms.example.test'],
        ['a receipt of a workspace', '/acme/submissions/uuid/6ae4ea8517e776a22c1a5b09', 'forms.example.test'],
        ["a respondent's submissions", '/acme/my-submissions', 'forms.example.test'],
        ['a workspace page', '/acme', 'forms.example.test'],
        ["a workspace's list of forms", '/acme/forms', 'forms.example.test'],
        ["a custom domain's front page", '/', 'forms.customer.test'],
        ["a custom domain's submissions", '/my-submissions', 'forms.customer.test'],
        ['a page that does not exist (the 404 page)', '/no/such/page/at/all', 'forms.example.test'],
        ['the form page of the dashboard host (not a form page there)', '/acme/dashboard/forms/x', 'admin.example.test'],
        ['a form-shaped path on the dashboard host (no published form there)', '/acme/forms/contact', 'admin.example.test']
    ])('lets only this site and the dashboard frame %s', async (_name, path, host) => {
        expect(await csp(path, host)).toBe(SELF_AND_DASHBOARD);
    });

    it.each([
        ['a published form', '/acme/forms/contact', 'forms.example.test'],
        ['its preview, which the builder frames', '/acme/forms/contact/preview', 'forms.example.test'],
        ['a published form on a custom domain', '/forms/contact', 'forms.customer.test'],
        ['a form with a trailing slash', '/acme/forms/contact/', 'forms.example.test']
    ])('sends no framing header on %s (as before)', async (_name, path, host) => {
        const reply = await answer(path, host);
        expect(reply.headers.get('content-security-policy')).toBeNull();
        expect(reply.headers.get('x-frame-options')).toBeNull();
    });

    it('sends one policy, and no X-Frame-Options', async () => {
        const reply = await answer('/acme/dashboard', 'admin.example.test');
        const value = reply.headers.get('content-security-policy') ?? '';
        expect(value).toBe(SELF_AND_DASHBOARD);
        // a second header would be joined with a comma
        expect(value).not.toContain(',');
        expect([...reply.headers.keys()].filter((key) => key === 'content-security-policy')).toHaveLength(1);
        expect(reply.headers.get('x-frame-options')).toBeNull();
    });

    it("names the dashboard from the running server's settings, with their scheme", async () => {
        env.DASHBOARD_DOMAIN = 'dash.example.test:8443';
        env.HTTP_SCHEME = 'http://';
        expect(await csp('/acme/dashboard', 'dash.example.test:8443')).toBe("frame-ancestors 'self' http://dash.example.test:8443");
    });

    it('works where the dashboard and the forms share one domain', async () => {
        env.DASHBOARD_DOMAIN = 'forms.example.test';
        expect(await csp('/acme/dashboard', 'forms.example.test')).toBe("frame-ancestors 'self' https://forms.example.test");
        expect(await csp('/acme/forms/contact', 'forms.example.test')).toBeNull();
        expect(await csp('/acme', 'forms.example.test')).toBe("frame-ancestors 'self' https://forms.example.test");
        expect(await csp('/login', 'forms.example.test')).toBe("frame-ancestors 'self' https://forms.example.test");
    });

    it('never writes an odd dashboard setting into the header', async () => {
        env.DASHBOARD_DOMAIN = 'x.example.test; script-src *';
        expect(await csp('/acme/dashboard', 'x.example.test')).toBe("frame-ancestors 'self'");
        env.DASHBOARD_DOMAIN = '';
        expect(await csp('/acme', 'forms.example.test')).toBe("frame-ancestors 'self'");
    });

    it('keeps the sign-in redirect for dashboard links, and frames nothing on it either', async () => {
        const reply = await answer('/acme/dashboard/forms', 'admin.example.test', '');
        expect(reply.status).toBe(307);
        expect(reply.headers.get('content-security-policy')).toBe(SELF_AND_DASHBOARD);
    });

    it('handles a workspace handle with a dot like any other', async () => {
        expect(await csp('/my.ws/dashboard', 'admin.example.test')).toBe(SELF_AND_DASHBOARD);
        expect(await csp('/my.ws', 'forms.example.test')).toBe(SELF_AND_DASHBOARD);
        expect(await csp('/my.ws/forms/contact', 'forms.example.test')).toBeNull();
    });

    it('does not redirect a visitor of a public page to sign-in', async () => {
        const reply = await answer('/acme', 'admin.example.test', '');
        expect(reply.status).toBe(200);
    });
});

describe('the plain rule', () => {
    it('names this site and the dashboard, for any path', () => {
        expect(frameAncestorsFor('https://admin.example.test')).toBe(SELF_AND_DASHBOARD);
        expect(frameAncestorsFor('')).toBe("frame-ancestors 'self'");
        expect(frameAncestorsFor('x; script-src *')).toBe("frame-ancestors 'self'");
    });
});

describe('the matcher', () => {
    const pattern = new RegExp(`^${config.matcher[0]}$`);
    it('covers pages, the 404 page and api routes, but not Next internals or static files', async () => {
        for (const path of ['/', '/login', '/acme/dashboard', '/acme/forms/contact', '/no/such/page', '/api/config', '/my.ws/dashboard']) expect(pattern.test(path), path).toBe(true);
        for (const path of ['/_next/static/chunks/a.js', '/_next/image', '/favicon.ico', '/embed.js', '/images/logo.png', '/manifest.webmanifest']) expect(pattern.test(path), path).toBe(false);
    });
});
