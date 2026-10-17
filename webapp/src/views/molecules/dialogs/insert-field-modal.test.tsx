import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { bestInsertMatch, filterInsertCatalog, insertCatalog } from '@app/constants/insert-field-catalog';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { InsertTarget } from '@app/store/jotai/insert-target';
import { store } from '@app/store/store';
import FieldSettings from '@app/views/organism/field-settings';

import InsertFieldComponent from './insert-field-modal';

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
    } as StandardFormFieldDto
];

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; active?: { id: string; index: number } | null; slide?: { id: string; index: number } | null; closed: number } = { closed: 0 };

function Editor({ settings = false, target, initial = pages }: { settings?: boolean; target?: InsertTarget; initial?: () => StandardFormFieldDto[] }) {
    const builder = useFormFieldsAtom();
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();
    seen.builder = builder;
    seen.active = activeFieldComponent;
    seen.slide = activeSlideComponent;
    React.useEffect(() => {
        builder.initFormFields(initial());
        setActiveSlideComponent({ id: 'page-1', index: 0 });
    }, []);
    if (!builder.formFields[0] || (activeSlideComponent?.id !== 'page-1' && !seen.active)) return null;
    return (
        <>
            <InsertFieldComponent formFields={builder.formFields} activeSlideComponent={activeSlideComponent} target={target} closeDropdown={() => (seen.closed += 1)} />
            {settings && activeFieldComponent && <FieldSettings />}
        </>
    );
}

function renderEditor(props: React.ComponentProps<typeof Editor> = {}) {
    seen.closed = 0;
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Editor {...props} />
            </Provider>
        </ReduxProvider>
    );
}

const search = () => screen.findByRole('combobox', { name: 'Search field types' });
const selectedOption = () => screen.getAllByRole('option').find((option) => option.getAttribute('aria-selected') === 'true');
const pageFields = (index = 0) => seen.builder!.formFields[index].properties!.fields!;

describe('insert menu: the catalog', () => {
    it('offers long text, image and video next to the other types', () => {
        const types = insertCatalog.map((item) => item.type);
        expect(types).toEqual(expect.arrayContaining([FieldTypes.LONG_TEXT, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT, FieldTypes.TEXT]));
        expect(new Set(types).size).toBe(types.length);
    });

    it('finds types by name, keyword and description, in category order', () => {
        expect(filterInsertCatalog('long').map((item) => item.type)).toEqual([FieldTypes.LONG_TEXT]);
        expect(filterInsertCatalog('youtube').map((item) => item.type)).toEqual([FieldTypes.VIDEO_CONTENT]);
        expect(filterInsertCatalog('stars').map((item) => item.type)).toEqual([FieldTypes.RATING]);
        expect(filterInsertCatalog('drop').map((item) => item.type)).toEqual([FieldTypes.DROP_DOWN]);
        expect(filterInsertCatalog('zzz')).toEqual([]);
        expect(filterInsertCatalog('').map((item) => item.category)[0]).toBe('Text');
        const numbers = filterInsertCatalog('number');
        expect(numbers[bestInsertMatch(numbers, 'number')].type).toBe(FieldTypes.NUMBER);
    });
});

describe('insert menu: search and keyboard', () => {
    it('groups the types under their categories, with a description each', async () => {
        renderEditor();
        await search();
        for (const name of ['Text', 'Choice', 'Scale', 'Date & number', 'Files', 'Layout & content']) {
            expect(screen.getByRole('group', { name })).toBeInTheDocument();
        }
        const longText = within(screen.getByRole('group', { name: 'Text' })).getByRole('option', { name: 'Long text' });
        expect(longText).toHaveAccessibleDescription('A longer answer over several lines');
    });

    it('filters as you type and highlights the first match', async () => {
        renderEditor();
        const input = await search();
        fireEvent.change(input, { target: { value: 'vid' } });
        expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([expect.stringContaining('Video')]);
        expect(selectedOption()).toHaveAccessibleName('Video');
        expect(input).toHaveAttribute('aria-activedescendant', selectedOption()!.id);

        fireEvent.change(input, { target: { value: 'nothing like this' } });
        expect(screen.queryAllByRole('option')).toHaveLength(0);
        expect(screen.getByText(/No field type matches/)).toBeInTheDocument();
    });

    it('moves the highlight with the arrow keys, wrapping at the ends', async () => {
        renderEditor();
        const input = await search();
        const options = screen.getAllByRole('option');
        expect(selectedOption()).toBe(options[0]);
        fireEvent.keyDown(input, { key: 'ArrowDown' });
        fireEvent.keyDown(input, { key: 'ArrowDown' });
        expect(selectedOption()).toBe(options[2]);
        fireEvent.keyDown(input, { key: 'ArrowUp' });
        expect(selectedOption()).toBe(options[1]);
        fireEvent.keyDown(input, { key: 'Home' });
        fireEvent.keyDown(input, { key: 'ArrowUp' });
        expect(selectedOption()).toBe(options[options.length - 1]);
        fireEvent.keyDown(input, { key: 'End' });
        fireEvent.keyDown(input, { key: 'ArrowDown' });
        expect(selectedOption()).toBe(options[0]);
    });

    it('Enter adds the highlighted type to the end of this page and selects it', async () => {
        renderEditor();
        const input = await search();
        fireEvent.change(input, { target: { value: 'long' } });
        await act(async () => fireEvent.keyDown(input, { key: 'Enter' }));

        const fields = pageFields();
        expect(fields).toHaveLength(4);
        expect(fields[3].type).toBe(FieldTypes.LONG_TEXT);
        expect(seen.active).toEqual({ id: fields[3].id, index: 3 });
        expect(seen.builder!.activeField?.id).toBe(fields[3].id);
        expect(seen.closed).toBe(1);
    });

    it('Shift+Enter adds it on a new page after this one', async () => {
        renderEditor();
        const input = await search();
        fireEvent.change(input, { target: { value: 'email' } });
        await act(async () => fireEvent.keyDown(input, { key: 'Enter', shiftKey: true }));

        expect(seen.builder!.formFields).toHaveLength(2);
        expect(seen.slide?.index).toBe(1);
        const inserted = pageFields(1)[0];
        expect(inserted.type).toBe(FieldTypes.EMAIL);
        expect(seen.active).toEqual({ id: inserted.id, index: 0 });
    });

    it('offers both placements as separate buttons, "this page" first', async () => {
        renderEditor();
        await search();
        const thisPage = screen.getByRole('button', { name: 'Add to this page' });
        const newPage = screen.getByRole('button', { name: 'Add on a new page' });
        expect(thisPage.compareDocumentPosition(newPage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        await act(async () => fireEvent.click(newPage));
        expect(seen.builder!.formFields).toHaveLength(2);
    });

    it('a click on a type adds it to this page', async () => {
        renderEditor();
        await search();
        await act(async () => fireEvent.click(screen.getByRole('option', { name: 'Image' })));
        const fields = pageFields();
        expect(fields[3].type).toBe(FieldTypes.IMAGE_CONTENT);
    });

    it('new questions get no title: nothing placeholder-like is saved', async () => {
        renderEditor();
        const input = await search();
        fireEvent.change(input, { target: { value: 'short' } });
        await act(async () => fireEvent.keyDown(input, { key: 'Enter' }));
        const inserted = pageFields()[3];
        expect(inserted.title).toBeUndefined();
        expect(inserted.value).toBeUndefined();
        expect(JSON.stringify(inserted)).not.toMatch(/Enter Question/);
    });

    it('the settings panel opens on the new question', async () => {
        renderEditor({ settings: true });
        await search();
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Add on a new page' })));
        expect(screen.getByText('Settings')).toBeInTheDocument();
        // not the previous page's last question
        expect(screen.queryByTitle('City')).toBeNull();
    });
});

describe('insert menu: at a position on the canvas', () => {
    const target = (extra: Partial<InsertTarget> = {}): InsertTarget => ({ slideId: 'page-1', slideIndex: 0, fieldIndex: 1, anchorId: 'x', ...extra });

    it('inserts at the target index and renumbers the page', async () => {
        renderEditor({ target: target() });
        const input = await search();
        expect(screen.getByRole('button', { name: 'Add here' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Add on a new page' })).toBeNull();
        fireEvent.change(input, { target: { value: 'date' } });
        await act(async () => fireEvent.keyDown(input, { key: 'Enter', shiftKey: true }));

        const fields = pageFields();
        expect(fields.map((field) => field.id)).toEqual(['q-1', expect.any(String), 'q-2', 'q-3']);
        expect(fields[1].type).toBe(FieldTypes.DATE);
        expect(fields.map((field) => field.index)).toEqual([0, 1, 2, 3]);
        expect(seen.active).toEqual({ id: fields[1].id, index: 1 });
        expect(seen.builder!.formFields).toHaveLength(1);
    });

    it('takes the place of the empty text block "/" was typed in', async () => {
        const withBlock = () => {
            const form = pages();
            form[0].properties!.fields!.splice(1, 0, { id: 'blank', index: 1, type: FieldTypes.TEXT } as StandardFormFieldDto);
            form[0].properties!.fields!.forEach((field, index) => (field.index = index));
            return form;
        };
        renderEditor({ initial: withBlock, target: target({ fieldIndex: 1, replaceFieldId: 'blank' }) });
        const input = await search();
        fireEvent.change(input, { target: { value: 'multiple' } });
        await act(async () => fireEvent.keyDown(input, { key: 'Enter' }));

        const fields = pageFields();
        expect(fields).toHaveLength(4);
        expect(fields.some((field) => field.id === 'blank')).toBe(false);
        expect(fields[1].type).toBe(FieldTypes.MULTIPLE_CHOICE);
    });
});

describe('field settings', () => {
    it('a selection that points at no question shows no settings instead of crashing', async () => {
        function Stale() {
            const builder = useFormFieldsAtom();
            const { setActiveSlideComponent } = useActiveSlideComponent();
            const { setActiveFieldComponent } = useActiveFieldComponent();
            React.useEffect(() => {
                builder.initFormFields(pages());
                setActiveSlideComponent({ id: 'page-1', index: 0 });
                setActiveFieldComponent({ id: 'gone', index: 7 });
            }, []);
            return <FieldSettings />;
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Stale />
                </Provider>
            </ReduxProvider>
        );
        expect(await screen.findByRole('button', { name: '‹ Back to page' })).toBeInTheDocument();
        expect(screen.queryByText('Settings')).toBeNull();
    });
});
