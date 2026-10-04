import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const sessionsQueryMock: { data: any[]; isLoading: boolean } = { data: [], isLoading: false };
const revokeSessionMock = vi.fn();
const revokeOthersMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetSessionsQuery: () => sessionsQueryMock,
        useRevokeSessionMutation: () => [revokeSessionMock],
        useRevokeOtherSessionsMutation: () => [revokeOthersMock, { isLoading: false }]
    };
});

import { store } from '@app/store/store';
import SessionsSection, { describeUserAgent } from './sessions-section';

const FIREFOX = 'Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0';
const SAFARI_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

const renderSection = () =>
    render(
        <ReduxProvider store={store}>
            <SessionsSection />
        </ReduxProvider>
    );

describe('SessionsSection (where the user is signed in)', () => {
    beforeEach(() => {
        revokeSessionMock.mockReset().mockResolvedValue({ data: { revoked: 1 } });
        revokeOthersMock.mockReset().mockResolvedValue({ data: { revoked: 1 } });
        sessionsQueryMock.data = [
            { id: 's1', userAgent: FIREFOX, current: true, createdAt: '2026-10-01T10:00:00Z' },
            { id: 's2', userAgent: SAFARI_IPHONE, current: false, createdAt: '2026-09-20T10:00:00Z' }
        ];
    });

    it('lists each session and marks this browser', () => {
        renderSection();
        expect(screen.getByText(/Firefox on Linux/)).toBeDefined();
        expect(screen.getByText(/This browser/)).toBeDefined();
        expect(screen.getByText(/Safari on iOS/)).toBeDefined();
    });

    it('signs out one other session', () => {
        renderSection();
        fireEvent.click(screen.getAllByRole('button', { name: 'Sign out' })[1]);
        expect(revokeSessionMock).toHaveBeenCalledWith('s2');
    });

    it('signs out everywhere else', () => {
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: /Sign out everywhere else/ }));
        expect(revokeOthersMock).toHaveBeenCalled();
    });

    it('offers "everywhere else" only when there are other sessions', () => {
        sessionsQueryMock.data = [{ id: 's1', userAgent: FIREFOX, current: true }];
        renderSection();
        expect(screen.queryByRole('button', { name: /Sign out everywhere else/ })).toBeNull();
    });
});

describe('describeUserAgent', () => {
    it('names common browsers and systems', () => {
        expect(describeUserAgent(FIREFOX)).toBe('Firefox on Linux');
        expect(describeUserAgent(SAFARI_IPHONE)).toBe('Safari on iOS');
        expect(describeUserAgent('curl/8.5.0')).toBe('curl');
        expect(describeUserAgent(undefined)).toBe('Unknown device');
    });
});
