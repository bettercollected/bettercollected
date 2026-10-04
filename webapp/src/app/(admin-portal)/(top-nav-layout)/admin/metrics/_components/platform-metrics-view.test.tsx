import React from 'react';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PlatformMetricsView from './platform-metrics-view';

const auth: { value: any } = { value: {} };
const query: { value: any } = { value: {} };
const querySkipped = vi.fn();

vi.mock('@app/store/hooks', () => ({ useAppSelector: (selector: any) => selector({ auth: auth.value }) }));
vi.mock('@app/store/platform-admin/api', () => ({
    useGetPlatformMetricsQuery: (_: unknown, options: { skip?: boolean }) => {
        querySkipped(!!options?.skip);
        return query.value;
    }
}));
vi.mock('@app/components/auth/auth-navbar', () => ({ default: () => <nav /> }));
vi.mock('react-chartjs-2', () => ({ Bar: () => <div data-testid="weekly-chart" /> }));

const metrics = {
    generatedAt: '2026-10-03T12:00:00Z',
    organizations: { total: 3212, newLast30Days: 6, disabled: 0 },
    users: null,
    formCreators: { total: 1815, activeLast30Days: 2 },
    formResponders: { identified: 7912, anonymousResponses: 33297 },
    forms: { total: 2612, published: 1918, newLast30Days: 6, byProvider: { self: 2001, google: 603, typeform: 8 } },
    responses: { total: 44004, last7Days: 5, last30Days: 126 },
    weekly: [
        { weekStart: '2026-09-21', newUsers: null, newOrganizations: 3, newForms: 4, responses: 13 },
        { weekStart: '2026-09-28', newUsers: null, newOrganizations: 0, newForms: 1, responses: 4 }
    ],
    errors: [{ source: 'users', message: 'The auth service did not answer; user counts are unavailable.' }]
};

describe('PlatformMetricsView', () => {
    beforeEach(() => {
        querySkipped.mockClear();
        query.value = { data: undefined, error: undefined, isLoading: false, isFetching: false, refetch: vi.fn() };
    });

    it('tells a signed-in non-admin they are not authorized, without asking the API', () => {
        auth.value = { id: 'u1', roles: ['FORM_CREATOR', 'FORM_RESPONDER'], isLoading: false };
        render(<PlatformMetricsView />);
        expect(screen.getByText('Not authorized')).toBeTruthy();
        expect(querySkipped).toHaveBeenLastCalledWith(true);
    });

    it('shows not authorized when the API refuses', () => {
        auth.value = { id: 'u1', roles: ['ADMIN'], isLoading: false };
        query.value = { ...query.value, error: { status: 403 } };
        render(<PlatformMetricsView />);
        expect(screen.getByText('Not authorized')).toBeTruthy();
    });

    it('shows the counts and says which ones are missing', () => {
        auth.value = { id: 'u1', roles: ['ADMIN'], isLoading: false };
        query.value = { ...query.value, data: metrics };
        render(<PlatformMetricsView />);
        expect(querySkipped).toHaveBeenLastCalledWith(false);
        expect(screen.getByText('Some counts are unavailable')).toBeTruthy();
        expect(screen.getByText('44,004')).toBeTruthy();
        expect(screen.getByText('Google Forms')).toBeTruthy();
        expect(screen.getByText('73%')).toBeTruthy(); // published share
        // new users are unavailable, so the chart opens on the next series
        expect(screen.getByTestId('weekly-chart')).toBeTruthy();
        expect(screen.getByRole('tab', { name: 'New organizations' }).getAttribute('data-state')).toBe('active');
    });

    it('shows the counts for a signed-in admin whose auth state still says loading', () => {
        // setAuth(user) after the status call leaves isLoading as it was (true)
        auth.value = { id: 'u1', roles: ['ADMIN'], isLoading: true };
        query.value = { ...query.value, data: metrics };
        render(<PlatformMetricsView />);
        expect(screen.queryByLabelText('Loading metrics')).toBeNull();
        expect(screen.getByText('44,004')).toBeTruthy();
    });
});
