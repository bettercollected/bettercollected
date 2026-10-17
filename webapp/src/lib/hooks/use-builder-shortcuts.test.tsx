import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { InsertTarget, useInsertTarget } from '@app/store/jotai/insert-target';
import { store } from '@app/store/store';

import { builderShortcutFor, isTypingTarget, useBuilderShortcuts } from './use-builder-shortcuts';

const pages = (): StandardFormFieldDto[] => [
    {
        id: 'page-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' },
                { id: 'q-2', index: 1, type: FieldTypes.EMAIL, title: 'Email' },
                { id: 'q-3', index: 2, type: FieldTypes.SHORT_TEXT, title: 'City' }
            ]
        }
    } as StandardFormFieldDto,
    { id: 'page-2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [] } } as StandardFormFieldDto
];

const seen: {
    builder?: ReturnType<typeof useFormFieldsAtom>;
    active?: { id: string; index: number } | null;
    slide?: { id: string; index: number } | null;
    target?: InsertTarget | null;
} = {};

function Builder({ select = 'q-2', openHelp }: { select?: string | null; openHelp: () => void }) {
    const builder = useFormFieldsAtom();
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();
    const { insertTarget } = useInsertTarget();
    useBuilderShortcuts({ openHelp });
    seen.builder = builder;
    seen.active = activeFieldComponent;
    seen.slide = activeSlideComponent;
    seen.target = insertTarget;
    React.useEffect(() => {
        builder.initFormFields(pages());
        setActiveSlideComponent({ id: 'page-1', index: 0 });
        if (select) setActiveFieldComponent({ id: select, index: pages()[0].properties!.fields!.findIndex((f) => f.id === select) });
    }, []);
    return (
        <>
            <div data-builder-canvas tabIndex={-1}>
                <button type="button">On the canvas</button>
                <input aria-label="Placeholder text" />
                <div contentEditable suppressContentEditableWarning aria-label="Title editor" role="textbox" />
            </div>
            <button type="button">Outside the canvas</button>
        </>
    );
}

const openHelp = vi.fn();
function renderBuilder(select: string | null = 'q-2') {
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Builder select={select} openHelp={openHelp} />
            </Provider>
        </ReduxProvider>
    );
}

const ids = () => seen.builder!.formFields[0].properties!.fields!.map((field) => field.id);
const press = (target: Element, init: KeyboardEventInit) => act(async () => fireEvent.keyDown(target, init));

beforeEach(() => openHelp.mockReset());

describe('isTypingTarget', () => {
    it('is true in text fields and editors, false on buttons and checkboxes', () => {
        const input = document.createElement('input');
        const checkbox = Object.assign(document.createElement('input'), { type: 'checkbox' });
        const editable = document.createElement('div');
        editable.setAttribute('contenteditable', 'true');
        const inside = document.createElement('span');
        editable.appendChild(inside);
        document.body.append(input, checkbox, editable);
        expect(isTypingTarget(input)).toBe(true);
        expect(isTypingTarget(document.createElement('textarea'))).toBe(true);
        expect(isTypingTarget(inside)).toBe(true);
        expect(isTypingTarget(checkbox)).toBe(false);
        expect(isTypingTarget(document.createElement('button'))).toBe(false);
        expect(isTypingTarget(null)).toBe(false);
    });
});

describe('builderShortcutFor', () => {
    const key = (k: string, extra: Partial<KeyboardEvent> = {}) => ({ key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, defaultPrevented: false, target: document.body, ...extra });

    it('maps the question shortcuts when something is selected', () => {
        expect(builderShortcutFor(key('ArrowUp', { altKey: true }), true)).toBe('move-up');
        expect(builderShortcutFor(key('ArrowDown', { altKey: true }), true)).toBe('move-down');
        expect(builderShortcutFor(key('d', { ctrlKey: true }), true)).toBe('duplicate');
        expect(builderShortcutFor(key('d', { metaKey: true }), true)).toBe('duplicate');
        expect(builderShortcutFor(key('Delete'), true)).toBe('delete');
        expect(builderShortcutFor(key('Backspace'), true)).toBe('delete');
        expect(builderShortcutFor(key('Delete'), false)).toBeNull();
    });

    it('maps page navigation, insert and help', () => {
        expect(builderShortcutFor(key('ArrowUp', { ctrlKey: true, altKey: true }), false)).toBe('previous-page');
        expect(builderShortcutFor(key('ArrowDown', { metaKey: true, altKey: true }), false)).toBe('next-page');
        expect(builderShortcutFor(key('k', { ctrlKey: true }), false)).toBe('open-insert');
        expect(builderShortcutFor(key('/'), false)).toBe('open-insert');
        expect(builderShortcutFor(key('?', { shiftKey: true }), false)).toBe('open-help');
    });

    it('never fires while typing, except Ctrl/Cmd+K', () => {
        const input = document.createElement('input');
        for (const event of [key('Delete'), key('Backspace'), key('d', { ctrlKey: true }), key('ArrowUp', { altKey: true }), key('/'), key('?'), key('ArrowDown', { ctrlKey: true, altKey: true })]) {
            expect(builderShortcutFor({ ...event, target: input }, true)).toBeNull();
        }
        expect(builderShortcutFor(key('k', { ctrlKey: true, target: input }), true)).toBe('open-insert');
    });

    it('leaves dialogs and already-handled keys alone', () => {
        const dialog = document.createElement('div');
        dialog.setAttribute('role', 'dialog');
        const button = document.createElement('button');
        dialog.appendChild(button);
        expect(builderShortcutFor(key('Delete', { target: button }), true)).toBeNull();
        expect(builderShortcutFor(key('k', { ctrlKey: true, target: button }), true)).toBeNull();
        expect(builderShortcutFor(key('Delete', { defaultPrevented: true }), true)).toBeNull();
    });
});

describe('builder shortcuts on the canvas', () => {
    it('Alt+↓ and Alt+↑ move the selected question', async () => {
        renderBuilder();
        const canvas = await screen.findByRole('button', { name: 'On the canvas' });
        await press(canvas, { key: 'ArrowDown', altKey: true });
        expect(ids()).toEqual(['q-1', 'q-3', 'q-2']);
        await press(canvas, { key: 'ArrowUp', altKey: true });
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3']);
    });

    it('Ctrl/Cmd+D duplicates it right after itself', async () => {
        renderBuilder();
        const canvas = await screen.findByRole('button', { name: 'On the canvas' });
        await press(canvas, { key: 'd', ctrlKey: true });
        expect(ids()).toHaveLength(4);
        expect(ids()[1]).toBe('q-2');
        expect(seen.builder!.formFields[0].properties!.fields![2].type).toBe(FieldTypes.EMAIL);
        expect(seen.active?.id).toBe(ids()[2]);
    });

    it('Delete removes it (with the undo message)', async () => {
        renderBuilder();
        const canvas = await screen.findByRole('button', { name: 'On the canvas' });
        await press(canvas, { key: 'Delete' });
        expect(ids()).toEqual(['q-1', 'q-3']);
    });

    it('does nothing while focus is in a text field or editor', async () => {
        renderBuilder();
        const input = await screen.findByRole('textbox', { name: 'Placeholder text' });
        const editor = screen.getByRole('textbox', { name: 'Title editor' });
        await press(input, { key: 'Backspace' });
        await press(input, { key: 'd', ctrlKey: true });
        await press(editor, { key: 'Delete' });
        await press(editor, { key: 'ArrowDown', altKey: true });
        await press(editor, { key: '/' });
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3']);
        expect(seen.target).toBeNull();
    });

    it('does not delete from outside the canvas', async () => {
        renderBuilder();
        const outside = await screen.findByRole('button', { name: 'Outside the canvas' });
        await press(outside, { key: 'Delete' });
        expect(ids()).toEqual(['q-1', 'q-2', 'q-3']);
    });

    it('/ opens the insert menu after the selected question', async () => {
        renderBuilder();
        const canvas = await screen.findByRole('button', { name: 'On the canvas' });
        await press(canvas, { key: '/' });
        expect(seen.target).toMatchObject({ slideId: 'page-1', slideIndex: 0, fieldIndex: 2, anchorId: 'scroll-field-q-2' });
    });

    it('Ctrl/Cmd+K with nothing selected opens it at the end of the page', async () => {
        renderBuilder(null);
        const canvas = await screen.findByRole('button', { name: 'On the canvas' });
        await press(canvas, { key: 'k', metaKey: true });
        expect(seen.target).toMatchObject({ fieldIndex: 3, anchorId: 'canvas-end-page-1' });
    });

    it('Ctrl/Cmd+Alt+↓/↑ go to the next and previous page', async () => {
        renderBuilder();
        const canvas = await screen.findByRole('button', { name: 'On the canvas' });
        await press(canvas, { key: 'ArrowDown', ctrlKey: true, altKey: true });
        expect(seen.slide).toEqual({ id: 'page-2', index: 1 });
        expect(seen.active).toBeNull();
        await press(canvas, { key: 'ArrowDown', ctrlKey: true, altKey: true });
        expect(seen.slide).toEqual({ id: 'thank-you-page', index: -20 });
        await press(canvas, { key: 'ArrowUp', ctrlKey: true, altKey: true });
        await press(canvas, { key: 'ArrowUp', ctrlKey: true, altKey: true });
        await press(canvas, { key: 'ArrowUp', ctrlKey: true, altKey: true });
        expect(seen.slide).toEqual({ id: 'welcome-page', index: -10 });
    });

    it('? opens the shortcut help', async () => {
        renderBuilder();
        const outside = await screen.findByRole('button', { name: 'Outside the canvas' });
        await press(outside, { key: '?', shiftKey: true });
        expect(openHelp).toHaveBeenCalledTimes(1);
    });
});
