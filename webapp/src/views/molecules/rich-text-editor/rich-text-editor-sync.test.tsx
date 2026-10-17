import React from 'react';

import { act, render, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';

import { RichTextEditor, titleNeedsSync } from './index';

// jsdom has no layout; ProseMirror measures for scrolling the selection into view.
beforeAll(() => {
    const rects = () => ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] }) as unknown as DOMRectList;
    const rect = () => ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }) as DOMRect;
    Range.prototype.getClientRects = rects;
    Range.prototype.getBoundingClientRect = rect;
    if (!Element.prototype.getClientRects) Element.prototype.getClientRects = rects;
    if (!document.elementFromPoint) document.elementFromPoint = () => null;
});

const doc = (text: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

const page = (title: any): StandardFormFieldDto[] => [
    { id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title }] } } as StandardFormFieldDto
];

let builder: ReturnType<typeof useFormFieldsAtom> | null = null;

function Canvas({ title }: { title: any }) {
    const atom = useFormFieldsAtom();
    builder = atom;
    React.useEffect(() => {
        atom.initFormFields(page(title));
    }, []);
    const slide = atom.formFields[0];
    const field = slide?.properties?.fields?.[0];
    if (!slide || slide.id !== 'page-1' || !field) return null;
    return <RichTextEditor field={field} slide={slide} />;
}

function renderCanvas(title: any) {
    const view = render(
        <ReduxProvider store={store}>
            <Provider>
                <Canvas title={title} />
            </Provider>
        </ReduxProvider>
    );
    const editorElement = () => view.container.querySelector('.ProseMirror') as (HTMLElement & { editor?: any }) | null;
    return { view, editorElement };
}

const storedTitle = () => builder!.formFields[0]?.properties?.fields?.[0]?.title;
const sleep = (ms: number) => act(() => new Promise((resolve) => setTimeout(resolve, ms)));

/** Type at the end of the title, as the creator would. */
async function typeText(element: HTMLElement & { editor?: any }, text: string) {
    await act(async () => {
        element.editor.chain().focus('end').insertContent(text).run();
    });
}

describe('canvas title editor', () => {
    it('saves what the creator types', async () => {
        const { editorElement } = renderCanvas(doc('Your name'));
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await typeText(editorElement()!, '?');
        await sleep(400);
        expect(JSON.stringify(storedTitle())).toContain('Your name?');
    });

    it('shows a title changed from outside (an AI edit) and never writes the old one back', async () => {
        const { editorElement } = renderCanvas(doc('Your name'));
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());

        await act(async () => builder!.updateTitle(0, 0, doc('Full legal name') as any));
        await waitFor(() => expect(editorElement()!.textContent).toBe('Full legal name'));
        await sleep(400);
        expect(storedTitle()).toEqual(doc('Full legal name'));
    });

    it('undo shows the earlier title, and the next keystroke builds on it', async () => {
        const { editorElement } = renderCanvas(doc('Name'));
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await typeText(editorElement()!, ' please');
        await sleep(400);
        expect(editorElement()!.textContent).toBe('Name please');

        await act(async () => builder!.undo());
        await waitFor(() => expect(editorElement()!.textContent).toBe('Name'));
        await sleep(400);
        expect(storedTitle()).toEqual(doc('Name'));

        await typeText(editorElement()!, '!');
        await sleep(400);
        expect(JSON.stringify(storedTitle())).toContain('Name!');
        expect(JSON.stringify(storedTitle())).not.toContain('please');
    });

    it('a keystroke still waiting to be saved does not override an undo', async () => {
        const { editorElement } = renderCanvas(doc('Name'));
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await typeText(editorElement()!, ' A');
        await sleep(400);
        await typeText(editorElement()!, 'B');
        // undo before the 'B' is saved
        await act(async () => builder!.undo());
        await sleep(400);
        expect(storedTitle()).toEqual(doc('Name'));
        expect(editorElement()!.textContent).toBe('Name');
    });
});

describe('titleNeedsSync', () => {
    it('compares the stored JSON with what the editor shows', () => {
        expect(titleNeedsSync(doc('a') as any, doc('a') as any)).toBe(false);
        expect(titleNeedsSync(doc('a') as any, doc('b') as any)).toBe(true);
        expect(titleNeedsSync('plain', doc('plain') as any)).toBe(true);
        expect(titleNeedsSync(undefined, doc('x') as any)).toBe(true);
    });
});
