import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';
import { selectAuth } from '@app/store/auth/slice';
import { selectWorkspace } from '@app/store/workspaces/slice';

import WelcomeBand from './welcome-band';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

const state: { forms: any; stats: any; firstName?: string } = { forms: undefined, stats: undefined };
vi.mock('@app/store/hooks', () => ({ useAppSelector: (selector: unknown) => (selector === selectAuth ? { firstName: state.firstName } : { id: 'w1', workspaceName: 'acme' }) }));
vi.mock('@app/store/workspaces/api', () => ({
    useGetWorkspaceFormsQuery: () => state.forms,
    useGetWorkspaceStatsQuery: () => state.stats
}));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true }) }));
vi.mock('@app/views/atoms/new-form-button', () => ({ default: ({ label }: { label?: string }) => <button type="button">{label ?? 'New form'}</button> }));

const forms = (items: any[], total = items.length) => ({ data: { items, total }, isLoading: false, isError: false });
const render_ = () =>
    render(
        <I18nProvider>
            <WelcomeBand />
        </I18nProvider>
    );

beforeEach(() => {
    push.mockClear();
    state.firstName = 'Ada';
    state.stats = { data: { deletionRequests: { pending: 0 } } };
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 10, 15, 9, 30));
});
afterEach(() => {
    cleanup();
    vi.useRealTimers();
});

describe('the welcome band', () => {
    it('greets by first name and time of day and offers the first form when there are none', () => {
        state.forms = forms([], 0);
        render_();
        expect(screen.getByRole('heading', { name: 'Good morning, Ada' })).toBeInTheDocument();
        expect(screen.getByTestId('welcome-band')).toHaveAttribute('data-state', 'no-forms');
        expect(screen.getByRole('button', { name: 'Create your first form' })).toBeInTheDocument();
    });

    it('greets without a name when there is none, in the afternoon and the evening', () => {
        state.forms = forms([], 0);
        state.firstName = undefined;
        vi.setSystemTime(new Date(2026, 10, 15, 14, 0));
        const { unmount } = render_();
        expect(screen.getByRole('heading', { name: 'Good afternoon' })).toBeInTheDocument();
        unmount();
        vi.setSystemTime(new Date(2026, 10, 15, 20, 0));
        render_();
        expect(screen.getByRole('heading', { name: 'Good evening' })).toBeInTheDocument();
    });

    it('says what is waiting and goes to the deletion requests', () => {
        state.forms = forms([{ formId: 'f1', title: 'Survey', isPublished: true }]);
        state.stats = { data: { deletionRequests: { pending: 2 } } };
        render_();
        expect(screen.getByText('2 deletion requests are waiting for you.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Review requests' }));
        expect(push).toHaveBeenCalledWith('/acme/dashboard/deletion-requests');
    });

    it('offers to finish a named draft', () => {
        state.forms = forms([{ formId: 'f9', title: 'Open day', isPublished: false }]);
        render_();
        expect(screen.getByText('“Open day” is still a draft. Finish it and publish when you are ready.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Open the draft' }));
        expect(push).toHaveBeenCalledWith('/acme/dashboard/forms/f9/edit');
    });

    it('has a calm default and never an exclamation mark', () => {
        state.forms = forms([{ formId: 'f1', title: 'Survey', isPublished: true }]);
        render_();
        expect(screen.getByTestId('welcome-band')).toHaveAttribute('data-state', 'ready');
        expect(screen.getByTestId('welcome-band').textContent).not.toContain('!');
    });

    it('shows nothing while the forms are loading', () => {
        state.forms = { data: undefined, isLoading: true, isError: false };
        const { container } = render_();
        expect(container).toBeEmptyDOMElement();
    });
});
