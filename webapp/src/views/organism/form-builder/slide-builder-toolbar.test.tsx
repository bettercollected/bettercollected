import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
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
// What the server says about the newer question types (its NEW_QUESTION_TYPES_ENABLED).
const served = vi.hoisted(() => ({ newQuestionTypesEnabled: false }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ newQuestionTypesEnabled: served.newQuestionTypesEnabled, can: () => true }) }));
afterEach(() => {
    served.newQuestionTypesEnabled = false;
    withTime = false;
    gatedType = FieldTypes.TIME;
});
// The rich-text editor and the field renderers are not what is tested here.
vi.mock('@app/views/molecules/rich-text-editor', () => ({
    RichTextEditor: ({ field }: { field: StandardFormFieldDto }) => <div data-testid={`editor-${field.id}`} />
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/plain-language-hints', () => ({ default: () => null }));
vi.mock('@app/lib/hooks/use-form-logo', () => ({ useBuilderFormLogo: () => null }));

// Set to add a time question as a fourth.
let withTime = false;
// The type of that question.
let gatedType: FieldTypes = FieldTypes.TIME;

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
                    { id: 'q-3', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Age' },
                    ...(withTime ? [{ id: 'q-4', index: 0, type: gatedType, title: 'Arrival' }] : [])
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

    it('cannot duplicate a time, day or currency question while the server does not take them', async () => {
        withTime = true;
        const { ids } = renderSelected('q-4');
        const duplicate = screen.getByRole('button', { name: 'Duplicate question' });
        expect(duplicate).toBeDisabled();
        expect(duplicate).toHaveAttribute('title', expect.stringContaining("can't be copied on this server yet"));
        act(() => void fireEvent.click(duplicate));
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3', 'q-4']);
        // what every question has stays: it can still be deleted
        expect(screen.getByRole('button', { name: 'Delete question' })).not.toBeDisabled();
    });

    it('duplicates it once the server takes them', async () => {
        served.newQuestionTypesEnabled = true;
        withTime = true;
        const { ids } = renderSelected('q-4');
        const duplicate = screen.getByRole('button', { name: 'Duplicate question' });
        expect(duplicate).not.toBeDisabled();
        act(() => void fireEvent.click(duplicate));
        expect(ids()).toHaveLength(5);
    });

    it.each([FieldTypes.DATE_RANGE, FieldTypes.TAGS])('cannot duplicate a %s question while the server does not take it, and can once it does', async (type) => {
        withTime = true;
        gatedType = type;
        const { ids } = renderSelected('q-4');
        const duplicate = screen.getByRole('button', { name: 'Duplicate question' });
        expect(duplicate).toBeDisabled();
        act(() => void fireEvent.click(duplicate));
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3', 'q-4']);
    });

    it.each([FieldTypes.DATE_RANGE, FieldTypes.TAGS])('duplicates a %s question once the server takes the newer types', async (type) => {
        withTime = true;
        gatedType = type;
        served.newQuestionTypesEnabled = true;
        const { ids } = renderSelected('q-4');
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Duplicate question' })));
        expect(ids()).toHaveLength(5);
    });
});
