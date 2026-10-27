import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { PublishProblem } from '@app/utils/publish-checks';

import enBuilder from '../../../../public/locales/en/builder.json';
import nlBuilder from '../../../../public/locales/nl/builder.json';
import PublishButton, { PublishProblemsDialog } from './publish-button';

const en = (enBuilder as any).PUBLISH_WORKSPACE_TITLE;
const nl = (nlBuilder as any).PUBLISH_WORKSPACE_TITLE;

const publishFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePublishV2FormMutation: () => [publishFormMock, { isLoading: false }] };
});
vi.mock('@app/lib/hooks/use-dialog-modal', () => ({ useDialogModal: () => ({ openDialogModal: vi.fn() }) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/ws/dashboard/forms/form-1/edit' }));
vi.mock('@app/views/molecules/form-builder/audo-save-form', () => ({ flushAutosave: async () => 'saved' }));

// Who the signed-in user is in the workspace: a workspace admin or owner may manage it, an editor may not.
const permissions = new Set<string>();
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => permissions.has(permission), permissions, isLoading: false, ready: true })
}));
const openBottomSheetModal = vi.fn();
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal, closeBottomSheetModal: vi.fn() }) }));

const PAGE = [{ id: 'page-1', index: 0, type: 'slide', properties: { fields: [{ id: 'q-1', index: 0, type: 'short_text', title: 'Name', description: '' }] } }];
const MISSING: PublishProblem = { code: 'workspace_title_missing', fieldId: '', message: 'Your workspace has no title yet.' };

const asAdmin = () => permissions.add('workspace.manage');

function renderButton() {
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <PublishButton fields={PAGE as any} />
            </Provider>
        </ReduxProvider>
    );
}

const setUp = (workspace: Record<string, unknown>) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', ...workspace } as any));
    store.dispatch(setForm({ formId: 'form-1', title: 'Sign-up', settings: { publishChecksVersion: 1 }, thankyouPage: [{ id: 'end-1', name: 'Thanks' }] } as any));
};

const clickPublish = async () => {
    await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
    });
};

describe('the workspace title is in both languages', () => {
    it('has the same keys in English and Dutch, and Dutch addresses the reader as "u"', () => {
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        for (const key of Object.keys(en)) {
            expect(en[key]).toBeTruthy();
            expect(nl[key]).toBeTruthy();
        }
        expect(`${nl.TEXT_MANAGE} ${nl.TEXT_MEMBER}`).toMatch(/\bUw\b/);
        expect(`${nl.TEXT_MANAGE} ${nl.TEXT_MEMBER}`).not.toMatch(/\b(je|jouw|jij)\b/i);
    });
});

describe('"Before you publish" with a workspace that has no title', () => {
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });
    const renderDialog = (canSetWorkspaceTitle: boolean) => {
        const onSetWorkspaceTitle = vi.fn();
        const onClose = vi.fn();
        const view = render(
            <PublishProblemsDialog
                blocking={[MISSING]}
                recommended={[]}
                onClose={onClose}
                onPublishAnyway={vi.fn()}
                onShowQuestion={vi.fn()}
                canShowQuestion={() => false}
                canSetWorkspaceTitle={canSetWorkspaceTitle}
                onSetWorkspaceTitle={onSetWorkspaceTitle}
            />
        );
        return { onSetWorkspaceTitle, view };
    };

    it('tells an admin what is missing and offers to set it', () => {
        const { onSetWorkspaceTitle } = renderDialog(true);
        expect(screen.getByTestId('publish-problems')).toHaveTextContent(en.TEXT_MANAGE);
        fireEvent.click(screen.getByRole('button', { name: en.ACTION }));
        expect(onSetWorkspaceTitle).toHaveBeenCalledTimes(1);
        // nothing to publish from here
        expect(screen.queryByRole('button', { name: 'Publish anyway' })).not.toBeInTheDocument();
    });

    it('tells someone who cannot set it to ask a workspace admin, without a way to set it', () => {
        renderDialog(false);
        expect(screen.getByTestId('publish-problems')).toHaveTextContent(en.TEXT_MEMBER);
        expect(en.TEXT_MEMBER).toMatch(/Ask a workspace admin/);
        expect(screen.queryByRole('button', { name: en.ACTION })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Show the question' })).not.toBeInTheDocument();
    });

    it('is worded in Dutch for an admin and for someone who is not', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        const admin = renderDialog(true);
        expect(screen.getByTestId('publish-problems')).toHaveTextContent(nl.TEXT_MANAGE);
        expect(screen.getByRole('button', { name: nl.ACTION })).toBeInTheDocument();
        admin.view.unmount();
        renderDialog(false);
        expect(screen.getByTestId('publish-problems')).toHaveTextContent(nl.TEXT_MEMBER);
        expect(screen.queryByRole('button', { name: nl.ACTION })).not.toBeInTheDocument();
    });
});

describe('publishing from a workspace without a title', () => {
    beforeEach(() => {
        publishFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1' } });
        openBottomSheetModal.mockReset();
        permissions.clear();
    });
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    for (const [name, title] of [
        ['no title', undefined],
        ['an empty title', ''],
        ['a title of only spaces', '   ']
    ] as const) {
        it(`stops before anything is sent when the workspace has ${name}`, async () => {
            setUp({ title, workspaceName: 'readable-handle' });
            renderButton();
            await clickPublish();
            const dialog = await screen.findByRole('dialog', { name: 'Before you publish' });
            expect(dialog).toHaveTextContent(en.TEXT_MEMBER);
            expect(publishFormMock).not.toHaveBeenCalled();
        });
    }

    it('gives an admin the way to set the title, which opens the workspace settings over the builder', async () => {
        asAdmin();
        setUp({ title: '' });
        renderButton();
        await clickPublish();
        const dialog = await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(dialog).toHaveTextContent(en.TEXT_MANAGE);
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: en.ACTION }));
        });
        expect(openBottomSheetModal).toHaveBeenCalledWith('WORKSPACE_SETTINGS', { initialIndex: 0 });
        expect(screen.queryByRole('dialog', { name: 'Before you publish' })).not.toBeInTheDocument();
        expect(publishFormMock).not.toHaveBeenCalled();
    });

    it('does not offer the way to someone without workspace.manage, an editor who can publish', async () => {
        permissions.add('form.edit');
        setUp({ title: '' });
        renderButton();
        await clickPublish();
        await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(screen.queryByRole('button', { name: en.ACTION })).not.toBeInTheDocument();
        expect(screen.getByRole('dialog')).toHaveTextContent('Ask a workspace admin');
    });

    it('publishes as before once the workspace has a title', async () => {
        setUp({ title: 'Acme Foundation' });
        renderButton();
        await clickPublish();
        await waitFor(() => expect(publishFormMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1' }));
        expect(screen.queryByRole('dialog', { name: 'Before you publish' })).not.toBeInTheDocument();
    });

    it('does not claim anything while the workspace is still loading: the server decides', async () => {
        store.dispatch(setWorkspace({} as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Sign-up', settings: { publishChecksVersion: 1 }, thankyouPage: [{ id: 'end-1', name: 'Thanks' }] } as any));
        renderButton();
        await clickPublish();
        expect(screen.queryByRole('dialog', { name: 'Before you publish' })).not.toBeInTheDocument();
    });

    it("shows the server's refusal the same way when the saved title was cleared meanwhile", async () => {
        setUp({ title: 'Acme Foundation' });
        publishFormMock.mockResolvedValue({ error: { status: 422, data: { code: 'form_not_publishable', problems: [{ code: 'workspace_title_missing', fieldId: null, message: 'Your workspace has no title yet.' }] } } });
        renderButton();
        await clickPublish();
        const dialog = await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(dialog).toHaveTextContent(en.TEXT_MEMBER);
        expect(publishFormMock).toHaveBeenCalledTimes(1);
    });
});
