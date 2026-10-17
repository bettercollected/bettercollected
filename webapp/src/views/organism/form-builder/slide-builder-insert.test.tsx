import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';

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

const page = (): StandardFormFieldDto => ({
    id: 'page-1',
    index: 0,
    type: FieldTypes.SLIDE,
    properties: {
        fields: [
            { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' },
            { id: 'q-2', index: 1, type: FieldTypes.EMAIL },
            { id: 'q-3', index: 2, type: FieldTypes.TEXT }
        ]
    }
});

let builder: ReturnType<typeof useFormFieldsAtom> | null = null;
let active: { id: string; index: number } | null = null;

function Canvas() {
    const atom = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();
    builder = atom;
    active = activeFieldComponent;
    React.useEffect(() => {
        atom.initFormFields([page()]);
        setActiveSlideComponent({ id: 'page-1', index: 0 });
    }, []);
    const slide = atom.formFields[0];
    if (!slide || slide.id !== 'page-1') return null;
    return <SlideBuilder slide={slide} />;
}

const renderCanvas = () =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Canvas />
            </Provider>
        </ReduxProvider>
    );

const ids = () => builder!.formFields[0].properties!.fields!.map((field) => field.id);

describe('the canvas', () => {
    it('names each field by its type and title, and lets Tab reach it', async () => {
        renderCanvas();
        const name = await screen.findByRole('group', { name: 'Short text: Name' });
        expect(name).toHaveAttribute('tabindex', '0');
        expect(screen.getByRole('group', { name: 'Email: untitled' })).toBeInTheDocument();
        expect(screen.getByRole('group', { name: 'Empty text block' })).toBeInTheDocument();
    });

    it('selects a field when it gets focus', async () => {
        renderCanvas();
        const email = await screen.findByRole('group', { name: 'Email: untitled' });
        await act(async () => fireEvent.focus(email));
        expect(active).toEqual({ id: 'q-2', index: 1 });
        expect(screen.getByRole('toolbar', { name: 'Question actions' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Duplicate question' })).toHaveAttribute('aria-keyshortcuts', 'Control+D Meta+D');
        expect(screen.getByRole('button', { name: 'Move question up' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Move question down' })).toBeInTheDocument();
    });

    it('a "+" between questions inserts the picked field at that position', async () => {
        renderCanvas();
        const plus = await screen.findByRole('button', { name: 'Add a field before question 2' });
        await act(async () => fireEvent.click(plus));
        const searchBox = await screen.findByRole('combobox', { name: 'Search field types' });
        fireEvent.change(searchBox, { target: { value: 'number' } });
        await act(async () => fireEvent.keyDown(searchBox, { key: 'Enter' }));

        expect(ids()).toEqual(['q-1', expect.any(String), 'q-2', 'q-3']);
        expect(builder!.formFields[0].properties!.fields![1].type).toBe(FieldTypes.NUMBER);
        expect(screen.queryByRole('combobox', { name: 'Search field types' })).toBeNull();
    });

    it('the "+" after the last question adds at the end of the page', async () => {
        renderCanvas();
        await act(async () => fireEvent.click(await screen.findByRole('button', { name: 'Add a field at the end of the page' })));
        await act(async () => fireEvent.click(screen.getByRole('option', { name: 'Video' })));
        expect(builder!.formFields[0].properties!.fields![3].type).toBe(FieldTypes.VIDEO_CONTENT);
    });

    it('Escape closes the menu without adding anything', async () => {
        renderCanvas();
        await act(async () => fireEvent.click(await screen.findByRole('button', { name: 'Add a field before question 1' })));
        const searchBox = await screen.findByRole('combobox', { name: 'Search field types' });
        await act(async () => fireEvent.keyDown(searchBox, { key: 'Escape' }));
        expect(screen.queryByRole('combobox', { name: 'Search field types' })).toBeNull();
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3']);
    });
});
