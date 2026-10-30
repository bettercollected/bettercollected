// The Google consent popup's callback page: it hands the result to the
// dashboard window that opened it, on the dashboard origin only.
import React from 'react';

import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleCallbackPage from './page';

const config = vi.hoisted(() => ({ HTTP_SCHEME: 'https://', DASHBOARD_DOMAIN: 'admin.example.test' }));
vi.mock('@app/configs/environments', () => ({ default: config }));

let search = '';
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(search) }));

const postMessage = vi.fn();

beforeEach(() => {
    config.HTTP_SCHEME = 'https://';
    config.DASHBOARD_DOMAIN = 'admin.example.test';
    postMessage.mockReset();
    vi.stubGlobal('opener', { postMessage });
    vi.spyOn(window, 'close').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
});

afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
});

const show = async () => {
    await act(async () => {
        render(<GoogleCallbackPage />);
    });
};

describe('the Google callback page', () => {
    it('posts to the dashboard origin, never to any origin', async () => {
        search = 'state=the-state&code=the-code&scope=x&authuser=0&prompt=consent';
        await show();

        expect(postMessage).toHaveBeenCalledTimes(1);
        expect(postMessage.mock.calls[0][1]).toBe('https://admin.example.test');
        expect(window.close).toHaveBeenCalled();
    });

    it('passes on only the code and the state', async () => {
        search = 'state=the-state&code=the-code&scope=x&authuser=0&prompt=consent';
        await show();

        expect(postMessage.mock.calls[0][0]).toEqual({ code: 'the-code', state: 'the-state' });
    });

    it("passes on Google's error", async () => {
        search = 'error=access_denied&state=the-state';
        await show();

        expect(postMessage).toHaveBeenCalledWith({ error: 'access_denied', state: 'the-state' }, 'https://admin.example.test');
    });

    it('uses the origin of a dashboard on a port', async () => {
        config.HTTP_SCHEME = 'http://';
        config.DASHBOARD_DOMAIN = 'localhost:3000';
        search = 'state=s&code=c';
        await show();

        expect(postMessage).toHaveBeenCalledWith({ code: 'c', state: 's' }, 'http://localhost:3000');
    });

    it('posts nothing when the dashboard origin is not configured', async () => {
        config.DASHBOARD_DOMAIN = '';
        search = 'state=s&code=c';
        await show();

        expect(postMessage).not.toHaveBeenCalled();
        expect(window.close).toHaveBeenCalled();
    });
});
