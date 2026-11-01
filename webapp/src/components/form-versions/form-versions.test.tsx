import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { FormVersionList, VersionCompare as VersionCompareData } from '@app/store/workspaces/form-versions-api';
import { axeViolations } from '@app/test/axe';

import VersionCompare from './version-compare';
import FormVersionsPage from './versions-page';

const list: { data: FormVersionList | undefined; isLoading: boolean; isError: boolean; error?: any } = { data: undefined, isLoading: false, isError: false };
const compare: { data: VersionCompareData | undefined; isLoading: boolean; isError: boolean; error?: any } = { data: undefined, isLoading: false, isError: false };
const restoreMock = vi.fn();
vi.mock('@app/store/workspaces/form-versions-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetFormVersionsQuery: () => ({ ...list, refetch: vi.fn() }),
        useCompareFormVersionsQuery: () => compare,
        useRestoreFormVersionMutation: () => [restoreMock, { isLoading: false }]
    };
});

let permissions = new Set<string>();
let switchOn = true;
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready: true, isLoading: false, formRevisionsUiEnabled: switchOn }) }));
vi.mock('@app/store/forms/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectForm: () => ({ formId: 'f1', settings: { provider: 'self' } }) };
});
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

const VERSIONS: FormVersionList = {
    versions: [
        { version: 2, publishedAt: '2026-10-30T10:00:00Z', publishedBy: { name: 'Sam Jansen', role: 'EDITOR', former: false }, current: true },
        { version: 1, publishedAt: '2026-10-01T09:00:00Z', publishedBy: null, current: false }
    ],
    draft: { updatedAt: '2026-10-31T08:00:00Z', hasUnpublishedChanges: true }
};

beforeEach(() => {
    list.data = VERSIONS;
    list.isLoading = false;
    list.isError = false;
    compare.data = undefined;
    compare.isError = false;
    compare.isLoading = false;
    switchOn = true;
    permissions = new Set([WorkspacePermission.FORM_READ, WorkspacePermission.FORM_EDIT]);
    restoreMock.mockReset();
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('the versions list', () => {
    it('lists each version with when and by whom, the live one marked', () => {
        render(<FormVersionsPage />, { wrapper });
        const two = screen.getByTestId('version-2');
        expect(within(two).getByRole('heading', { name: 'Version 2' })).toBeInTheDocument();
        expect(within(two).getByText('Live')).toBeInTheDocument();
        expect(within(two).getByText(/Sam Jansen \(Editor\)/)).toBeInTheDocument();
        expect(within(screen.getByTestId('version-1')).getByText(/Not recorded/)).toBeInTheDocument();
        expect(within(screen.getByTestId('version-1')).queryByText('Live')).not.toBeInTheDocument();
    });

    it('says "a former member" for someone who left, never an id', () => {
        list.data = { ...VERSIONS, versions: [{ version: 3, publishedAt: '2026-10-31T10:00:00Z', publishedBy: { former: true }, current: true }] };
        render(<FormVersionsPage />, { wrapper });
        expect(screen.getByText(/A former member/)).toBeInTheDocument();
    });

    it('links View, Compare with previous and the draft comparison', () => {
        render(<FormVersionsPage />, { wrapper });
        expect(screen.getByRole('link', { name: 'View version 2' })).toHaveAttribute('href', '/acme/dashboard/forms/f1/versions/2');
        expect(screen.getByRole('link', { name: 'Compare version 2 with the version before it' })).toHaveAttribute('href', '/acme/dashboard/forms/f1/versions/compare?from=1&to=2');
        // the first version has nothing before it
        expect(screen.queryByRole('link', { name: 'Compare version 1 with the version before it' })).not.toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Compare the live version with the draft' })).toHaveAttribute('href', '/acme/dashboard/forms/f1/versions/compare?from=2&to=draft');
        expect(screen.getByText('Has changes that are not published yet')).toBeInTheDocument();
    });

    it('offers Restore only with form.edit', () => {
        permissions = new Set([WorkspacePermission.FORM_READ]);
        render(<FormVersionsPage />, { wrapper });
        expect(screen.queryByRole('button', { name: /Restore version/ })).not.toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'View version 1' })).toBeInTheDocument();
    });

    it('says the page is off, and asks nothing, while the server switch is off', () => {
        switchOn = false;
        render(<FormVersionsPage />, { wrapper });
        expect(screen.getByRole('status')).toHaveTextContent('The versions page is not switched on on this server.');
        expect(screen.queryByTestId('form-versions')).not.toBeInTheDocument();
    });

    it('shows a failed load with a way to try again', () => {
        list.data = undefined;
        list.isError = true;
        list.error = { status: 500 };
        render(<FormVersionsPage />, { wrapper });
        expect(screen.getByRole('alert')).toHaveTextContent('The versions could not be loaded.');
        expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        const { container } = render(<FormVersionsPage />, { wrapper });
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('restoring', () => {
    const open = (version = 1) => fireEvent.click(screen.getByRole('button', { name: `Restore version ${version}` }));

    it('asks first, says what is replaced and what is not restored, and sends the draft stamp', async () => {
        restoreMock.mockResolvedValue({ data: { restoredVersion: 1 } });
        render(<FormVersionsPage />, { wrapper });
        open(1);
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).getByText('Restore version 1?')).toBeInTheDocument();
        expect(within(dialog).getByText(/Your draft has changes that are not published yet/)).toBeInTheDocument();
        expect(within(dialog).getByText(/Not restored: the logo and cover image/)).toBeInTheDocument();
        expect(restoreMock).not.toHaveBeenCalled();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Restore into the draft' }));
        await waitFor(() => expect(restoreMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', version: 1, expectedUpdatedAt: '2026-10-31T08:00:00Z', replaceDraft: true }));
        expect(await screen.findByText(/Version 1 is now your draft/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Open the builder' })).toHaveAttribute('href', '/acme/dashboard/forms/f1/edit');
    });

    it('does not claim a replacement when the draft has nothing unpublished', async () => {
        list.data = { ...VERSIONS, draft: { updatedAt: '2026-10-31T08:00:00Z', hasUnpublishedChanges: false } };
        restoreMock.mockResolvedValue({ data: { restoredVersion: 1 } });
        render(<FormVersionsPage />, { wrapper });
        open(1);
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).queryByText(/Your draft has changes/)).not.toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Restore into the draft' }));
        await waitFor(() => expect(restoreMock).toHaveBeenCalledWith(expect.objectContaining({ replaceDraft: false })));
    });

    it('says why a refused restore was refused, in the dialog', async () => {
        restoreMock.mockResolvedValue({ error: { status: 422, data: { code: 'field_rules_disabled' } } });
        render(<FormVersionsPage />, { wrapper });
        open(1);
        const dialog = await screen.findByRole('alertdialog');
        fireEvent.click(within(dialog).getByRole('button', { name: 'Restore into the draft' }));
        expect(await within(dialog).findByRole('alert')).toHaveTextContent('This version has field rules, and field rules are not switched on on this server.');
    });

    it('speaks Dutch to the staff', async () => {
        await i18n.changeLanguage('nl');
        render(<FormVersionsPage />, { wrapper });
        expect(screen.getByRole('heading', { name: 'Versie 2' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Versie 1 terugzetten' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).getByText('Versie 1 terugzetten?')).toBeInTheDocument();
        expect(within(dialog).getByText(/Uw concept bevat wijzigingen/)).toBeInTheDocument();
    });
});

describe('the comparison', () => {
    it('words each change under its heading', () => {
        compare.data = {
            fromVersion: '1',
            toVersion: '2',
            changed: true,
            truncated: false,
            entries: [
                { kind: 'form_title_changed', scope: 'form', ref: null, title: null, params: { before: 'One', after: 'Two' } },
                { kind: 'question_added', scope: 'question', ref: 'c', title: 'Email', params: { type: 'email', page: 1 } },
                { kind: 'required_changed', scope: 'question', ref: 'a', title: 'Name', params: { required: true } }
            ]
        };
        render(<VersionCompare from="1" to="2" />, { wrapper });
        expect(screen.getByText('Changes from version 1 to version 2')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'The form' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Questions' })).toBeInTheDocument();
        expect(screen.getByText('The form title changed from “One” to “Two”.')).toBeInTheDocument();
        expect(screen.getByText('“Name” is now required.')).toBeInTheDocument();
        expect(screen.getByText(/Settings such as purpose, retention and who may edit are not part of a version/)).toBeInTheDocument();
    });

    it('says plainly when nothing differs', () => {
        compare.data = { fromVersion: '2', toVersion: 'draft', changed: false, truncated: false, entries: [] };
        render(<VersionCompare from="2" to="draft" />, { wrapper });
        expect(screen.getByText('Changes from version 2 to the draft')).toBeInTheDocument();
        expect(screen.getByText('No difference in content.')).toBeInTheDocument();
    });

    it('says when a version cannot be compared, and when it was cut short', () => {
        compare.isError = true;
        compare.error = { status: 422, data: { code: 'not_comparable' } };
        const { unmount } = render(<VersionCompare from="1" to="2" />, { wrapper });
        expect(screen.getByRole('alert')).toHaveTextContent('These cannot be compared');
        unmount();
        compare.isError = false;
        compare.data = { fromVersion: '1', toVersion: '2', changed: true, truncated: true, entries: [{ kind: 'theme_changed', scope: 'form', ref: null, title: null, params: {} }] };
        render(<VersionCompare from="1" to="2" />, { wrapper });
        expect(screen.getByText('Only the first 1 changes are shown.')).toBeInTheDocument();
    });

    it('refuses an address it cannot read instead of asking the server', () => {
        render(<VersionCompare from="abc" to="2" />, { wrapper });
        expect(screen.getByRole('alert')).toHaveTextContent('This version does not exist.');
    });

    it('has no accessibility violations', async () => {
        compare.data = { fromVersion: '1', toVersion: '2', changed: true, truncated: false, entries: [{ kind: 'theme_changed', scope: 'form', ref: null, title: null, params: {} }] };
        const { container } = render(<VersionCompare from="1" to="2" />, { wrapper });
        expect(await axeViolations(container)).toEqual([]);
    });
});
