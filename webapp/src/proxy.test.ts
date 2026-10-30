import { NextRequest } from 'next/server';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { proxy, signInRedirect } from './proxy';

const env = vi.hoisted(() => ({ DASHBOARD_DOMAIN: 'admin.example.test', HTTP_SCHEME: 'https://' }));
vi.mock('@app/configs/environments', () => ({ default: env }));

const request = (path: string, { host = 'admin.example.test', cookie, proto }: { host?: string; cookie?: string; proto?: string } = {}) =>
    new NextRequest(`http://internal:3000${path}`, { headers: { host, ...(cookie ? { cookie } : {}), ...(proto ? { 'x-forwarded-proto': proto } : {}) } });

describe('proxy: deep links to a workspace dashboard', () => {
    afterEach(() => {
        env.HTTP_SCHEME = 'https://';
        vi.unstubAllEnvs();
    });

    it('sends a visitor without a session to the sign-in page with the page as the target', () => {
        const reply = signInRedirect(request('/acme/dashboard/forms/f1/responses?page=2'));
        expect(reply?.status).toBe(307);
        const location = new URL(reply?.headers.get('location') ?? '');
        // the configured scheme and dashboard domain, never the internal address
        expect(location.origin).toBe('https://admin.example.test');
        expect(location.pathname).toBe('/login');
        expect([...location.searchParams.keys()]).toEqual(['redirect_to']);
        expect(location.searchParams.get('redirect_to')).toBe('/acme/dashboard/forms/f1/responses?page=2');
    });

    it('takes the scheme from HTTP_SCHEME, not from the request inside the container', () => {
        expect(new URL(signInRedirect(request('/acme/dashboard', { proto: 'http' }))?.headers.get('location') ?? '').protocol).toBe('https:');
        env.HTTP_SCHEME = 'http://';
        expect(new URL(signInRedirect(request('/acme/dashboard'))?.headers.get('location') ?? '').protocol).toBe('http:');
        env.HTTP_SCHEME = 'gopher://';
        expect(new URL(signInRedirect(request('/acme/dashboard'))?.headers.get('location') ?? '').protocol).toBe('https:');
    });

    it('puts the sign-in page under the deploy base path; the target stays a path of the app', () => {
        vi.stubEnv('BASE_DEPLOY_PATH', '/app/');
        const location = new URL(signInRedirect(request('/acme/dashboard'))?.headers.get('location') ?? '');
        expect(location.pathname).toBe('/app/login');
        // the sign-in page's redirect() adds the base path itself
        expect(location.searchParams.get('redirect_to')).toBe('/acme/dashboard');
    });

    it('leaves a request with a session cookie alone', () => {
        expect(signInRedirect(request('/acme/dashboard', { cookie: 'Authorization=x' }))).toBeNull();
        expect(signInRedirect(request('/acme/dashboard', { cookie: 'RefreshToken=x' }))).toBeNull();
        expect(proxy(request('/acme/dashboard', { cookie: 'RefreshToken=x' })).headers.get('location')).toBeNull();
    });

    it('acts on the dashboard host only', () => {
        expect(signInRedirect(request('/acme/dashboard', { host: 'forms.customer.test' }))).toBeNull();
    });
});
