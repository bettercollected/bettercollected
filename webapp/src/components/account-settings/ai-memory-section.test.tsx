import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Partial-mock only the hooks — the store keeps the real workspacesApi
// reducer/middleware (registered at store creation).
const memoryQueryMock: { data: any[]; isLoading: boolean } = { data: [], isLoading: false };
const addMemoryMock = vi.fn();
const deleteMemoryMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetAIMemoryQuery: () => memoryQueryMock,
        useAddAIMemoryEntryMutation: () => [addMemoryMock, { isLoading: false }],
        useDeleteAIMemoryEntryMutation: () => [deleteMemoryMock]
    };
});

import { store } from '@app/store/store';
import AIMemorySection from './ai-memory-section';

const renderSection = () =>
    render(
        <ReduxProvider store={store}>
            <AIMemorySection />
        </ReduxProvider>
    );

describe('AIMemorySection (the AI Memory page body)', () => {
    beforeEach(() => {
        addMemoryMock.mockReset().mockResolvedValue({ data: [] });
        deleteMemoryMock.mockReset().mockResolvedValue({ data: [] });
        memoryQueryMock.data = [];
    });

    it('lists every remembered entry with its provenance', () => {
        memoryQueryMock.data = [
            { id: 'm1', text: 'Always use 7-step rating scales', source: 'extracted' },
            { id: 'm2', text: 'Keep pages under 5 questions', source: 'manual' }
        ];
        renderSection();

        expect(screen.getByText('Always use 7-step rating scales')).toBeDefined();
        expect(screen.getByText(/Learned from a session/)).toBeDefined();
        expect(screen.getByText('Keep pages under 5 questions')).toBeDefined();
        expect(screen.getByText(/Added by you/)).toBeDefined();
    });

    it('shows an honest empty state', () => {
        renderSection();
        expect(screen.getByText(/Nothing remembered yet/)).toBeDefined();
    });

    it('adds a preference through the input', async () => {
        renderSection();
        fireEvent.change(screen.getByPlaceholderText(/Add a preference/), { target: { value: 'Use British English' } });
        fireEvent.click(screen.getByRole('button', { name: /Add/ }));
        expect(addMemoryMock).toHaveBeenCalledWith(expect.objectContaining({ body: { text: 'Use British English' } }));
    });

    it('forgets an entry in one click', () => {
        memoryQueryMock.data = [{ id: 'm1', text: 'Always use 7-step rating scales', source: 'extracted' }];
        renderSection();
        fireEvent.click(screen.getByLabelText('Forget "Always use 7-step rating scales"'));
        expect(deleteMemoryMock).toHaveBeenCalledWith(expect.objectContaining({ entry_id: 'm1' }));
    });
});
