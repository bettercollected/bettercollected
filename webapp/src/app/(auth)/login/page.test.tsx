// @vitest-environment node
import { getURLFromRedirectError } from 'next/dist/client/components/redirect';
import { isRedirectError } from 'next/dist/client/components/redirect-error';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const FORM_HOST = 'forms.example';
const DASHBOARD_HOST = 'admin.example';

let requestHost = FORM_HOST;
vi.mock('next/headers', () => ({
    headers: async () => new Headers({ host: requestHost }),
    cookies: async () => ({ get: (name: string) => (name === 'Authorization' ? { name, value: 'access' } : undefined) })
}));
vi.mock('@app/configs/environments', () => ({
    default: { INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://api.internal', DASHBOARD_DOMAIN: DASHBOARD_HOST }
}));
vi.mock('../_components/login-view', () => ({ default: () => null }));

const { default: LoginPage } = await import('./page');

/** Where the sign-in page sends the browser, or null when it renders the sign-in form. */
async function redirectTarget(redirectTo: string | string[] | undefined): Promise<string | null> {
    try {
        await LoginPage({ searchParams: Promise.resolve({ type: 'responder', workspace_id: 'w1', redirect_to: redirectTo }) });
        return null;
    } catch (e) {
        if (isRedirectError(e)) return getURLFromRedirectError(e);
        throw e;
    }
}

describe('sign-in page with a signed-in session off the dashboard host', () => {
    const fetchMock = vi.fn();

    beforeEach(() => {
        requestHost = FORM_HOST;
        fetchMock.mockReset();
        // the session is valid
        fetchMock.mockResolvedValue(new Response(JSON.stringify({ id: 'user-1' }), { status: 200 }));
        vi.stubGlobal('fetch', fetchMock);
        vi.spyOn(console, 'error').mockImplementation(() => {});
    });
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    it('goes back to the page of this site the sign-in started from', async () => {
        expect(await redirectTarget('/acme/forms/x')).toBe('/acme/forms/x');
        expect(await redirectTarget('/acme/forms/x?lang=nl')).toBe('/acme/forms/x?lang=nl');
    });

    it.each(['https://evil.example/', '//evil.example/', '/\\evil.example/', '/\t/evil.example/', 'javascript:alert(1)', ['https://evil.example/', '/acme']])(
        'never sends the browser to another site: %j',
        async (redirectTo) => {
            expect(await redirectTarget(redirectTo)).toBeNull();
        }
    );

    it('never sends the browser to another site from a custom domain either', async () => {
        requestHost = 'forms.acme.example';
        expect(await redirectTarget('//evil.example/')).toBeNull();
        expect(await redirectTarget('https://evil.example/')).toBeNull();
        expect(await redirectTarget('/forms/x')).toBe('/forms/x');
    });

    it('shows the sign-in form when no target was given', async () => {
        expect(await redirectTarget(undefined)).toBeNull();
    });
});
