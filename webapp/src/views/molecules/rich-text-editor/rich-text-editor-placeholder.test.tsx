import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { InsertTarget, useInsertTarget } from '@app/store/jotai/insert-target';
import { store } from '@app/store/store';

import { RichTextEditor, initialTitleContent, titlePlaceholder } from './index';

// jsdom has no layout; ProseMirror measures for scrolling the selection into view.
beforeAll(() => {
    const rects = () => ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] }) as unknown as DOMRectList;
    const rect = () => ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }) as DOMRect;
    Range.prototype.getClientRects = rects;
    Range.prototype.getBoundingClientRect = rect;
    if (!Element.prototype.getClientRects) Element.prototype.getClientRects = rects;
    if (!document.elementFromPoint) document.elementFromPoint = () => null;
});

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; target?: InsertTarget | null } = {};

function Canvas({ field }: { field: Partial<StandardFormFieldDto> }) {
    const atom = useFormFieldsAtom();
    const { insertTarget } = useInsertTarget();
    seen.builder = atom;
    seen.target = insertTarget;
    React.useEffect(() => {
        atom.initFormFields([
            {
                id: 'page-1',
                index: 0,
                type: FieldTypes.SLIDE,
                properties: { fields: [{ id: 'q-0', index: 0, type: FieldTypes.SHORT_TEXT, title: 'First' }, { id: 'q-1', index: 1, type: FieldTypes.SHORT_TEXT, ...field } as StandardFormFieldDto] }
            } as StandardFormFieldDto
        ]);
    }, []);
    const slide = atom.formFields[0];
    const current = slide?.properties?.fields?.[1];
    if (!slide || slide.id !== 'page-1' || !current) return null;
    return <RichTextEditor field={current} slide={slide} />;
}

function renderCanvas(field: Partial<StandardFormFieldDto>) {
    const view = render(
        <ReduxProvider store={store}>
            <Provider>
                <Canvas field={field} />
            </Provider>
        </ReduxProvider>
    );
    const editorElement = () => view.container.querySelector('.ProseMirror') as (HTMLElement & { editor?: any }) | null;
    return { view, editorElement };
}

const stored = () => seen.builder!.formFields[0]?.properties?.fields?.[1];
const sleep = (ms: number) => act(() => new Promise((resolve) => setTimeout(resolve, ms)));

describe('untitled questions on the canvas', () => {
    it('show a placeholder hint, and save nothing for it', async () => {
        const { editorElement } = renderCanvas({ title: undefined });
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        const editor = editorElement()!;
        expect(editor.textContent).toBe('');
        expect(editor.querySelector('[data-placeholder]')?.getAttribute('data-placeholder')).toBe(titlePlaceholder(FieldTypes.SHORT_TEXT));

        await act(async () => {
            editor.editor.commands.focus();
            editor.editor.commands.blur();
        });
        await sleep(400);
        expect(stored()?.title).toBeUndefined();
        expect(JSON.stringify(seen.builder!.formFields)).not.toMatch(/Enter Question/);
    });

    it('save only what the creator types', async () => {
        const { editorElement } = renderCanvas({ title: undefined });
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await act(async () => {
            editorElement()!.editor.chain().focus('end').insertContent('Where do you live?').run();
        });
        await sleep(400);
        expect(JSON.stringify(stored()?.title)).toContain('Where do you live?');
        expect(JSON.stringify(stored()?.title)).not.toMatch(/Enter Question|Type a question/);
    });

    it('a legacy plain title shows as the title, not the placeholder', () => {
        expect(initialTitleContent({ type: FieldTypes.SHORT_TEXT, value: 'Your city' })).toContain('Your city');
        expect(initialTitleContent({ type: FieldTypes.SHORT_TEXT })).toBe('');
        expect(initialTitleContent({ type: FieldTypes.YES_NO, value: 'Yes' })).toBe('');
    });
});

describe('"/" in an empty title', () => {
    it('opens the insert menu after this question instead of typing "/"', async () => {
        const { editorElement } = renderCanvas({ title: undefined });
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await act(async () => fireEvent.keyDown(editorElement()!, { key: '/' }));
        expect(seen.target).toEqual({ slideId: 'page-1', slideIndex: 0, fieldIndex: 2, replaceFieldId: undefined, anchorId: 'title-editor-q-1', returnFocusId: 'title-editor-q-1' });
        expect(editorElement()!.textContent).toBe('');
    });

    it('in an empty text block, the picked field takes its place', async () => {
        const { editorElement } = renderCanvas({ type: FieldTypes.TEXT, title: undefined });
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await act(async () => fireEvent.keyDown(editorElement()!, { key: '/' }));
        expect(seen.target).toMatchObject({ fieldIndex: 1, replaceFieldId: 'q-1' });
    });

    it('types a "/" as usual once the title has text', async () => {
        const { editorElement } = renderCanvas({ title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Yes' }] }] } as any });
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await act(async () => fireEvent.keyDown(editorElement()!, { key: '/' }));
        expect(seen.target).toBeNull();
    });
});

describe('title formatting toolbar', () => {
    it('is a toolbar of labelled buttons that say whether they are on', async () => {
        const { editorElement } = renderCanvas({ title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi', marks: [{ type: 'bold' }] }] }] } as any });
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await act(async () => {
            editorElement()!.editor.commands.focus('end');
        });
        const toolbar = screen.getByRole('toolbar', { name: 'Text formatting' });
        expect(within(toolbar).getByRole('button', { name: 'Bold' })).toHaveAttribute('aria-pressed', 'true');
        expect(within(toolbar).getByRole('button', { name: 'Italic' })).toHaveAttribute('aria-pressed', 'false');
        expect(within(toolbar).getByRole('button', { name: 'Underline' })).toHaveAttribute('aria-pressed', 'false');
        expect(within(toolbar).getByRole('button', { name: 'Larger text' })).toBeInTheDocument();
        expect(within(toolbar).getByRole('button', { name: 'Smaller text' })).toBeInTheDocument();
        expect(screen.getByRole('textbox', { name: 'Question title' })).toBe(editorElement());
    });
});
