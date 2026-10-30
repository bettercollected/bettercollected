import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeleteResponseModal, { isSameSitePath } from './delete-response-modal';

const push = vi.fn();
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace }) }));
const closeModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ closeModal }) }));
const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));
const remove = vi.fn();
vi.mock('@app/store/workspaces/api', () => ({ useDeleteResponseMutation: () => [remove] }));
vi.mock('@Components/common/generic-half-modal', () => ({ default: ({ positiveAction, positiveText }: any) => <button onClick={positiveAction}>{positiveText}</button> }));

const workspace = { id: 'ws1', workspaceName: 'acme' };

describe('delete response confirmation', () => {
    beforeEach(() => {
        push.mockReset();
        replace.mockReset();
        toast.mockReset();
        closeModal.mockReset();
        remove.mockReset();
    });

    it('goes back to the list after deleting from a response page, replacing the deleted page in history', async () => {
        remove.mockResolvedValue({ data: { ok: true } });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="/acme/dashboard/forms/f1/responses" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(replace).toHaveBeenCalledWith('/acme/dashboard/forms/f1/responses'));
        expect(push).not.toHaveBeenCalled();
        expect(remove).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', responseId: 'r1' });
        expect(closeModal).toHaveBeenCalled();
    });

    it('stays where it is when nothing says where to go, and when the delete failed', async () => {
        remove.mockResolvedValue({ data: { ok: true } });
        const { unmount } = render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(closeModal).toHaveBeenCalled());
        expect(replace).not.toHaveBeenCalled();
        unmount();

        remove.mockResolvedValue({ error: { status: 500 } });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="/acme/dashboard/forms/f1/responses" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.objectContaining({ variant: 'destructive' })));
        expect(replace).not.toHaveBeenCalled();
    });

    it.each(['//evil.example.com', '/\\evil.example.com', '\\\\evil.example.com', 'https://evil.example.com/x', 'javascript:alert(1)', '/acme\\..\\x'])('never follows an address that is not a path of this site: %s', async (address) => {
        remove.mockResolvedValue({ data: { ok: true } });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo={address} />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(closeModal).toHaveBeenCalled());
        expect(replace).not.toHaveBeenCalled();
        expect(push).not.toHaveBeenCalled();
    });

    it('takes only a path of this origin', () => {
        expect(isSameSitePath('/acme/dashboard/deletion-requests')).toBe(true);
        expect(isSameSitePath('/\\evil.example.com')).toBe(false);
        expect(isSameSitePath(undefined)).toBe(false);
        expect(isSameSitePath(42)).toBe(false);
    });

    it('tells the page when the delete starts, and again when it failed', async () => {
        const onDeleting = vi.fn();
        remove.mockResolvedValue({ error: { status: 500 } });
        const { unmount } = render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="/acme/dashboard/forms/f1/responses" onDeleting={onDeleting} />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(onDeleting.mock.calls).toEqual([[true], [false]]));
        unmount();

        onDeleting.mockReset();
        remove.mockImplementation(async () => {
            // the page has stopped asking for the response before the delete (and its invalidation) lands
            expect(onDeleting).toHaveBeenCalledWith(true);
            return { data: { ok: true } };
        });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="/acme/dashboard/forms/f1/responses" onDeleting={onDeleting} />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(replace).toHaveBeenCalled());
        expect(onDeleting.mock.calls).toEqual([[true]]);
    });
});
