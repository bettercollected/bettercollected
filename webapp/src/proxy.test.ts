import { NextRequest } from 'next/server';

import { describe, expect, it, vi } from 'vitest';

import { proxy, signInRedirect } from './proxy';

vi.mock('@app/configs/environments', () => ({ default: { DASHBOARD_DOMAIN: 'admin.example.test' } }));

const request = (path: string, { host = 'admin.example.test', cookie }: { host?: string; cookie?: string } = {}) => new NextRequest(`http://internal:3000${path}`, { headers: { host, ...(cookie ? { cookie } : {}) } });

describe('proxy: deep links to a workspace dashboard', () => {
    it('sends a visitor without a session to the sign-in page with the page as the target', () => {
        const reply = signInRedirect(request('/acme/dashboard/forms/f1/responses?page=2'));
        expect(reply?.status).toBe(307);
        const location = new URL(reply?.headers.get('location') ?? '');
        expect(location.origin).toBe('http://admin.example.test');
        expect(location.pathname).toBe('/login');
        expect([...location.searchParams.keys()]).toEqual(['redirect_to']);
        expect(location.searchParams.get('redirect_to')).toBe('/acme/dashboard/forms/f1/responses?page=2');
    });

    it('keeps https behind the TLS proxy', () => {
        const reply = signInRedirect(new NextRequest('http://internal:3000/acme/dashboard', { headers: { host: 'admin.example.test', 'x-forwarded-proto': 'https' } }));
        expect(reply?.headers.get('location')).toBe('https://admin.example.test/login?redirect_to=%2Facme%2Fdashboard');
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
