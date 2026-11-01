import React from 'react';

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import OptionListEditor from './option-list-editor';

const api = vi.hoisted(() => ({ updated: [] as any[], imported: [] as any[] }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
// one object, as the store gives one until the list changes
const LIST = vi.hoisted(() => ({
    id: 'l1',
    name: 'Cities',
    order: 'manual',
    itemCount: 2,
    totalItems: 2,
    revision: 3,
    formsUsing: 0,
    usedBy: [],
    items: [
        { id: 'li1', label: 'Amsterdam', group: 'NL' },
        { id: 'li2', label: 'Berlin', group: 'DE' }
    ]
}));
vi.mock('@app/store/option-lists/api', () => ({
    useGetOptionListQuery: () => ({ data: LIST }),
    useUpdateOptionListMutation: () => [
        (args: any) => {
            api.updated.push(args);
            return Promise.resolve({ data: { ...args, totalItems: 2 } });
        },
        { isLoading: false }
    ],
    useDeleteOptionListMutation: () => [vi.fn()],
    useImportOptionListCsvMutation: () => [
        (args: any) => {
            api.imported.push(args);
            return Promise.resolve({ data: { totalItems: 1 } });
        }
    ],
    useExportOptionListCsvMutation: () => [vi.fn()]
}));

const show = (onClose = vi.fn()) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'ws' }));
    render(
        <ReduxProvider store={store}>
            <OptionListEditor listId="l1" canEdit onClose={onClose} />
        </ReduxProvider>
    );
    return onClose;
};

describe('the list editor', () => {
    beforeEach(() => {
        api.updated = [];
        api.imported = [];
        i18n.changeLanguage('en');
    });
    afterEach(() => {
        cleanup();
        vi.restoreAllMocks();
    });

    it('saves the items against the revision it read', async () => {
        show();
        fireEvent.change(screen.getByLabelText('Label of item 1'), { target: { value: 'Amsterdam-Zuid' } });
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Save' })));
        expect(api.updated[0]).toMatchObject({ workspaceId: 'ws-1', listId: 'l1', expectedRevision: 3 });
        expect(api.updated[0].items[0]).toEqual({ id: 'li1', label: 'Amsterdam-Zuid', group: 'NL' });
    });

    it('asks before leaving with unsaved edits, and leaves at once without any', () => {
        const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
        const onClose = show();
        fireEvent.click(screen.getByRole('button', { name: 'Back to the lists' }));
        expect(confirm).not.toHaveBeenCalled();
        expect(onClose).toHaveBeenCalledTimes(1);
        fireEvent.change(screen.getByLabelText('Label of item 2'), { target: { value: 'Bonn' } });
        fireEvent.click(screen.getByRole('button', { name: 'Back to the lists' }));
        expect(confirm).toHaveBeenCalledWith('You have changes that are not saved. Leave without saving them?');
        expect(onClose).toHaveBeenCalledTimes(1);
        confirm.mockReturnValue(true);
        fireEvent.click(screen.getByRole('button', { name: 'Back to the lists' }));
        expect(onClose).toHaveBeenCalledTimes(2);
    });

    it('asks before an import replaces unsaved edits, and sends the revision with the file', async () => {
        const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
        show();
        const file = new File(['label\r\nA\r\n'], 'list.csv', { type: 'text/csv' });
        Object.defineProperty(file, 'text', { value: async () => 'label\r\nA\r\n' });
        fireEvent.change(screen.getByLabelText('Label of item 1'), { target: { value: 'Edited' } });
        fireEvent.change(screen.getByTestId('list-import'), { target: { files: [file] } });
        expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Importing a file replaces the items'));
        expect(api.imported).toEqual([]);
        confirm.mockReturnValue(true);
        await act(async () => fireEvent.change(screen.getByTestId('list-import'), { target: { files: [file] } }));
        await waitFor(() => expect(api.imported[0]).toMatchObject({ listId: 'l1', expectedRevision: 3, csv: 'label\r\nA\r\n' }));
    });
});
