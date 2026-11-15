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
// the member's permissions, by name; a test narrows them to play a Viewer, an Editor and so on
const permissions: { held: Set<string> | 'all' } = { held: 'all' };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (permission: string) => permissions.held === 'all' || permissions.held.has(permission) }) }));
vi.mock('@app/views/atoms/new-form-button', () => ({ default: ({ label }: { label?: string }) => <button type="button">{label ?? 'New form'}</button> }));

const DRAFT = { formId: 'f9', title: 'Open day', isPublished: false, builderVersion: 'v2', settings: { provider: 'self' } };
const forms = (items: any[], total = items.length) => ({ data: { items, total }, isLoading: false, isError: false });
const render_ = () =>
    render(
        <I18nProvider>
            <WelcomeBand />
        </I18nProvider>
    );

beforeEach(() => {
    permissions.held = 'all';
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
    it('only greets when there are no forms: no sentence and no button (the empty state below has the one action)', () => {
        state.forms = forms([], 0);
        render_();
        expect(screen.getByRole('heading', { name: 'Good morning, Ada' })).toBeInTheDocument();
        expect(screen.getByTestId('welcome-band')).toHaveAttribute('data-state', 'no-forms');
        expect(screen.queryByRole('button')).toBeNull();
        expect(screen.getByTestId('welcome-band').querySelector('p')).toBeNull();
        expect(screen.getByTestId('welcome-band').querySelector('svg')).toBeNull();
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
        state.forms = forms([DRAFT]);
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

    describe('by role', () => {
        const as = (...held: string[]) => {
            permissions.held = new Set(held);
        };

        it('a Viewer is not told to start a form and gets no empty action area', () => {
            as();
            state.forms = forms([{ formId: 'f1', title: 'Survey', isPublished: true }]);
            render_();
            const band = screen.getByTestId('welcome-band');
            expect(band).toHaveTextContent('Your forms are listed below.');
            expect(band).not.toHaveTextContent('Start a new form');
            expect(screen.queryByRole('button')).toBeNull();
            // no empty wrapper where the action would be
            expect(band.querySelectorAll('div.mt-1')).toHaveLength(0);
        });

        it('a Viewer with a draft in the list is not offered it, and neither are requests', () => {
            as();
            state.forms = forms([DRAFT]);
            state.stats = { data: { deletionRequests: { pending: 3 } } };
            render_();
            expect(screen.getByTestId('welcome-band')).toHaveAttribute('data-state', 'ready');
            expect(screen.queryByRole('button')).toBeNull();
        });

        it('an Editor is offered the draft, opened with the editor URL, but not the requests', () => {
            as('form.edit', 'form.create');
            state.forms = forms([DRAFT]);
            state.stats = { data: { deletionRequests: { pending: 3 } } };
            render_();
            fireEvent.click(screen.getByRole('button', { name: 'Open the draft' }));
            expect(push).toHaveBeenCalledWith('/acme/dashboard/forms/f9/edit');
        });

        it('a member who may create forms but not edit them is offered a new form, not the draft', () => {
            as('form.create');
            state.forms = forms([DRAFT]);
            render_();
            expect(screen.getByRole('button', { name: 'New form' })).toBeInTheDocument();
            expect(screen.queryByRole('button', { name: 'Open the draft' })).toBeNull();
        });

        it('a Privacy officer is offered the requests', () => {
            as('privacy.manage');
            state.forms = forms([{ formId: 'f1', title: 'Survey', isPublished: true }]);
            state.stats = { data: { deletionRequests: { pending: 1 } } };
            render_();
            expect(screen.getByText('1 deletion request is waiting for you.')).toBeInTheDocument();
            expect(screen.getByRole('button', { name: 'Review requests' })).toBeInTheDocument();
        });

        it('does not offer a draft the builder cannot open (imported or old builder)', () => {
            state.forms = forms([{ formId: 'g1', title: 'Imported', isPublished: false, builderVersion: 'v1', settings: { provider: 'google' } }]);
            render_();
            expect(screen.getByTestId('welcome-band')).toHaveAttribute('data-state', 'ready');
        });
    });
});
