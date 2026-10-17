import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeAll, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useField, usePageShell } from '@app/store/jotai/entity-hooks';
import { formDocAtom, resetFromServerAtom, undoAtom } from '@app/store/jotai/form-document';
import { store as reduxStore } from '@app/store/store';

import { RichTextEditor } from './index';

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
                    { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: doc('Name') },
                    { id: 'q-2', index: 1, type: FieldTypes.SHORT_TEXT, title: doc('City') }
                ]
            }
        }
    ] as StandardFormFieldDto[]
});

/** One question's title editor, on the narrow hooks as the canvas renders it. */
function Title({ id }: { id: string }) {
    const field = useField(id);
    const slide = usePageShell('page-1');
    if (!field || !slide) return null;
    return <RichTextEditor field={field} slide={slide} />;
}

function renderTitle(id: string, hiddenFields?: string[]) {
    const jotai = createStore();
    jotai.set(resetFromServerAtom, { ...form(), ...(hiddenFields ? { hiddenFields } : {}) } as any);
    const view = render(
        <ReduxProvider store={reduxStore}>
            <Provider store={jotai}>
                <Title id={id} />
            </Provider>
        </ReduxProvider>
    );
    const editorElement = () => view.container.querySelector('.ProseMirror') as (HTMLElement & { editor?: any }) | null;
    const stored = () => jotai.get(formDocAtom).fields![0].properties!.fields!.find((field) => field.id === id)!.title;
    return { view, jotai, editorElement, stored };
}

const typeText = (element: HTMLElement & { editor?: any }, text: string) =>
    act(async () => {
        element.editor.chain().focus('end').insertContent(text).run();
    });

describe('title editor when it unmounts', () => {
    it('writes what the debounce still held', async () => {
        const { view, editorElement, stored } = renderTitle('q-1');
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await typeText(editorElement()!, ' and surname');
        // left right away, before the 300 ms debounce wrote it
        expect(JSON.stringify(stored())).not.toContain('surname');
        view.unmount();
        expect(JSON.stringify(stored())).toContain('Name and surname');
    });

    it('does not write text that an undo replaced since', async () => {
        const { view, jotai, editorElement, stored } = renderTitle('q-1');
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        await typeText(editorElement()!, ' A');
        await act(() => new Promise((resolve) => setTimeout(resolve, 400)));
        await typeText(editorElement()!, 'B');
        await act(async () => void jotai.set(undoAtom));
        await waitFor(() => expect(editorElement()!.textContent).toBe('Name'));
        view.unmount();
        expect(stored()).toEqual(doc('Name'));
    });
});

describe('the "@ Answer" menu', () => {
    it('shows only when there is something to pipe, and lists it when opened', async () => {
        const first = renderTitle('q-1');
        await waitFor(() => expect(first.editorElement()?.editor).toBeTruthy());
        expect(screen.queryByRole('button', { name: /@ Answer/ })).toBeNull();
        first.view.unmount();

        const second = renderTitle('q-2');
        await waitFor(() => expect(second.editorElement()?.editor).toBeTruthy());
        const button = await screen.findByRole('button', { name: /@ Answer/ });
        act(() => void fireEvent.click(button));
        const menu = screen.getByRole('group', { name: 'Insert an earlier answer' });
        expect(menu).toHaveTextContent('Name');
        expect(menu).not.toHaveTextContent('City');
    });

    it('a hidden field is something to pipe', async () => {
        const { editorElement } = renderTitle('q-1', ['utm_source']);
        await waitFor(() => expect(editorElement()?.editor).toBeTruthy());
        act(() => void fireEvent.click(screen.getByRole('button', { name: /@ Answer/ })));
        expect(screen.getByRole('group', { name: 'Insert an earlier answer' })).toHaveTextContent('utm_source');
    });
});
