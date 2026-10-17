import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { formDocAtom, resetFromServerAtom } from '@app/store/jotai/form-document';
import { store as reduxStore } from '@app/store/store';

import SlideBuilder from './slide-builder';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/f1/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));
// The rich-text editor and the field renderers are not what is tested here.
vi.mock('@app/views/molecules/rich-text-editor', () => ({
    RichTextEditor: ({ field }: { field: StandardFormFieldDto }) => <div data-testid={`editor-${field.id}`} />
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/plain-language-hints', () => ({ default: () => null }));
vi.mock('@app/lib/hooks/use-form-logo', () => ({ useBuilderFormLogo: () => null }));

// Stored indexes that do not match the positions: the toolbar must go by id.
const form = () => ({
    formId: 'form-1',
    title: 'Form',
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [
                    { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' },
                    { id: 'q-2', index: 0, type: FieldTypes.SHORT_TEXT, title: 'City' },
                    { id: 'q-3', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Age' }
                ]
            }
        }
    ]
});

function renderSelected(fieldId: string) {
    const jotai = createStore();
    jotai.set(resetFromServerAtom, form() as any);
    jotai.set(activeSlideAtom, { id: 'page-1', index: 0 });
    jotai.set(activeFieldAtom, { id: fieldId, index: 0 });
    render(
        <ReduxProvider store={reduxStore}>
            <Provider store={jotai}>
                <SlideBuilder pageId="page-1" />
                <Toaster />
            </Provider>
        </ReduxProvider>
    );
    const ids = () => jotai.get(formDocAtom).fields![0].properties!.fields!.map((field) => field.id);
    return { jotai, ids };
}

describe('the selected question toolbar acts on that question, by id', () => {
    it('deletes it', async () => {
        const { ids } = renderSelected('q-2');
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Delete question' })));
        expect(ids()).toEqual(['q-1', 'q-3']);
    });

    it('duplicates it right after itself', async () => {
        const { ids } = renderSelected('q-3');
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Duplicate question' })));
        expect(ids()).toHaveLength(4);
        expect(ids().slice(0, 3)).toEqual(['q-1', 'q-2', 'q-3']);
    });

    it('moves it up and down from where it is', async () => {
        const { ids } = renderSelected('q-2');
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Move question up' })));
        expect(ids()).toEqual(['q-2', 'q-1', 'q-3']);
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Move question down' })));
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3']);
    });
});
