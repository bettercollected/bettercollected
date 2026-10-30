import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeleteResponseModal from './delete-response-modal';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
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
        closeModal.mockReset();
        remove.mockReset();
    });

    it('goes back to the list after deleting from a response page', async () => {
        remove.mockResolvedValue({ data: { ok: true } });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="/acme/dashboard/forms/f1/responses" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(push).toHaveBeenCalledWith('/acme/dashboard/forms/f1/responses'));
        expect(remove).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', responseId: 'r1' });
        expect(closeModal).toHaveBeenCalled();
    });

    it('stays where it is when nothing says where to go, and when the delete failed', async () => {
        remove.mockResolvedValue({ data: { ok: true } });
        const { unmount } = render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(closeModal).toHaveBeenCalled());
        expect(push).not.toHaveBeenCalled();
        unmount();

        remove.mockResolvedValue({ error: { status: 500 } });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="/acme/dashboard/forms/f1/responses" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.objectContaining({ variant: 'destructive' })));
        expect(push).not.toHaveBeenCalled();
    });

    it('never follows an address that is not a path of this site', async () => {
        remove.mockResolvedValue({ data: { ok: true } });
        render(<DeleteResponseModal workspace={workspace} formId="f1" responseId="r1" navigateTo="//evil.example.com" />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
        await waitFor(() => expect(closeModal).toHaveBeenCalled());
        expect(push).not.toHaveBeenCalled();
    });
});
