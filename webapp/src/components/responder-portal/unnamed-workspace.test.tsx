// A workspace with no title has its id as handle. The respondent pages and the
// form editor's navbar never show it: a readable name, else a translated label.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { SubmissionProvider } from '@app/components/responder-portal/submission-context';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import NavBar from '@app/views/molecules/form-builder/navbar';

import SubmissionLayoutClient from './submission-layout-client';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => '/x', useSearchParams: () => new URLSearchParams(window.location.search) }));

const ID = '68f1c0a2b3d4e5f607182930';
const workspace = (over: Record<string, unknown>) => store.dispatch(setWorkspace({ id: 'ws1', ownerId: ID, workspaceName: ID, title: '', ...over } as any));

const renderHeader = (lang = '') => {
    window.history.replaceState(null, '', `/${lang}`);
    return render(
        <ReduxProvider store={store}>
            <SubmissionProvider value={{ data: undefined, isLoading: true, isError: false, handleRequestForDeletion: () => {}, hasCustomDomain: false, workspaceName: ID, submissionId: 's1' }}>
                <SubmissionLayoutClient>
                    <p>content</p>
                </SubmissionLayoutClient>
            </SubmissionProvider>
        </ReduxProvider>
    );
};

afterEach(() => window.history.replaceState(null, '', '/'));

describe('the submission page header', () => {
    it('says "This workspace" instead of the id, in English and Dutch', () => {
        workspace({});
        const { unmount } = renderHeader();
        expect(screen.getByText('This workspace')).toBeInTheDocument();
        expect(document.body).not.toHaveTextContent(ID);
        unmount();
        renderHeader('?lang=nl');
        expect(screen.getByText('Deze werkruimte')).toBeInTheDocument();
        expect(document.body).not.toHaveTextContent(ID);
    });

    it('still shows the title when there is one', () => {
        workspace({ title: 'Vereniging Voorbeeld' });
        renderHeader();
        expect(screen.getByText('Vereniging Voorbeeld')).toBeInTheDocument();
    });
});

describe('the form editor navbar', () => {
    it('names the back button without the id and uses a neutral initial', () => {
        workspace({});
        render(
            <ReduxProvider store={store}>
                <NavBar />
            </ReduxProvider>
        );
        const back = screen.getByRole('button', { name: 'Back to workspace forms' });
        expect(back).toHaveTextContent('W');
        expect(document.body).not.toHaveTextContent(ID);
    });

    it('names the workspace and takes its initial from the title', () => {
        workspace({ title: 'Vereniging Voorbeeld' });
        render(
            <ReduxProvider store={store}>
                <NavBar />
            </ReduxProvider>
        );
        expect(screen.getByRole('button', { name: 'Back to Vereniging Voorbeeld forms' })).toHaveTextContent('V');
    });
});
