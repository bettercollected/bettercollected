import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { useOpenAIProposal } from '@app/store/jotai/ai-proposal';

import LeftDrawer from './left-drawer';

// The overlay is measured by the browser; jsdom has no layout, so drags are
// measured on the rows themselves (mocked below).
vi.mock('@dnd-kit/core', async (importOriginal) => ({ ...(await importOriginal<typeof import('@dnd-kit/core')>()), DragOverlay: () => null }));
// The "+" popover pulls in template queries; not under test here.
vi.mock('./add-slide/add-slide-popover', () => ({ default: () => <button type="button" aria-label="Add page" /> }));

const q = (id: string, title: string, extra: Partial<StandardFormFieldDto> = {}) => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, ...extra }) as StandardFormFieldDto;
const pages = (): StandardFormFieldDto[] =>
    [
        { id: 'p1', type: FieldTypes.SLIDE, properties: { sectionTitle: 'About you', fields: [q('name', 'Your name'), q('email', 'Your email', { type: FieldTypes.EMAIL })] } },
        { id: 'p2', type: FieldTypes.SLIDE, properties: { fields: [q('city', 'Your city'), q('ref', 'Reference', { internal: true })] } },
        { id: 'p3', type: FieldTypes.SLIDE, properties: { fields: [] } }
    ].map((slide, index) => ({ ...slide, index, properties: { ...slide.properties, fields: slide.properties.fields.map((f, i) => ({ ...f, index: i })) } })) as StandardFormFieldDto[];

const seen: any = {};
function Editor() {
    const builder = useFormFieldsAtom();
    const slide = useActiveSlideComponent();
    const field = useActiveFieldComponent();
    const ending = useActiveThankYouPageComponent();
    const endingState = useFormState();
    const { setFormState } = endingState;
    Object.assign(seen, { builder, slide, field, ending, endingState });
    React.useEffect(() => {
        builder.initFormFields(pages());
        setFormState((prev) => ({ ...prev, thankyouPage: [{ title: 'Thanks!' }, { title: 'Sorry, not eligible' }] }));
    }, []);
    return <LeftDrawer formFields={builder.formFields} activeSlideComponent={slide.activeSlideComponent} />;
}

// An open AI proposal that changes "Your name" on page 1 and adds a page.
function OpenProposal() {
    const { setOpenProposal } = useOpenAIProposal();
    React.useEffect(() => {
        setOpenProposal({
            proposal: { id: 'x', ops: [], form: {}, diff: {}, results: [], summary: '' },
            groups: [
                { key: 'page:p1', label: 'Page 1', pageId: 'p1', changes: [{ key: '0:0', opIndex: 0, text: "Made 'Your name' required", kind: 'changed', fieldId: 'name', pageId: 'p1' }] },
                { key: 'page:new', label: 'Page 4', pageId: 'new', changes: [{ key: '1:0', opIndex: 1, text: 'Added page 4', kind: 'added', pageId: 'new' }] }
            ]
        });
    }, []);
    return null;
}

const renderOutline = (withProposal = false) =>
    render(
        <Provider>
            {withProposal && <OpenProposal />}
            <Editor />
            <Toaster />
        </Provider>
    );

const fieldIds = (page: number) => seen.builder.formFields[page].properties.fields.map((f: StandardFormFieldDto) => f.id);

// jsdom has no layout: give every outline row a 40px slot in document order.
const originalRect = Element.prototype.getBoundingClientRect;
beforeAll(() => {
    Element.prototype.getBoundingClientRect = function () {
        const rows = Array.from(document.querySelectorAll('[data-outline-row]'));
        const i = rows.indexOf(this as Element);
        if (i < 0) return originalRect.call(this);
        const top = i * 40;
        return { x: 0, y: top, top, left: 0, width: 240, height: 36, right: 240, bottom: top + 36, toJSON: () => ({}) } as DOMRect;
    };
});
afterAll(() => {
    Element.prototype.getBoundingClientRect = originalRect;
});

const tick = () => act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
async function keyboardMove(handleName: string, steps: Array<'ArrowDown' | 'ArrowUp'>) {
    const handle = screen.getByRole('button', { name: handleName });
    handle.focus();
    await act(async () => fireEvent.keyDown(handle, { code: 'Space', key: ' ' }));
    await tick();
    for (const code of steps) {
        await act(async () => fireEvent.keyDown(document, { code, key: code }));
        await tick();
    }
    await act(async () => fireEvent.keyDown(document, { code: 'Space', key: ' ' }));
    await tick();
}

describe('builder outline', () => {
    it('marks the pages and questions an open AI proposal changes', async () => {
        renderOutline(true);
        await tick();
        const page = within(screen.getByRole('list', { name: 'Pages' })).getByRole('button', { name: /^About you/ });
        expect(within(page).getByText('1 proposed AI change')).toBeDefined();
        const name = screen.getByRole('button', { name: /^Your name/ });
        expect(name.textContent).toContain('changed by an AI proposal');
        expect(screen.getByRole('button', { name: /^Your city/ }).textContent).not.toContain('AI');
    });

    it('shows pages by section title or number, their questions, and status chips', async () => {
        renderOutline();
        await tick();
        const pagesList = screen.getByRole('list', { name: 'Pages' });
        expect(within(pagesList).getByRole('button', { name: /^About you/ })).toBeInTheDocument();
        expect(within(pagesList).getByRole('button', { name: /^Page 2/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Your city' })).toBeInTheDocument();
        // Chips: empty page, identity question without a reason, internal question.
        expect(within(pagesList).getByRole('button', { name: /^Page 3.*Empty/ })).toBeInTheDocument();
        expect(within(pagesList).getByRole('button', { name: /^About you.*Missing why we ask/ })).toBeInTheDocument();
        expect(within(pagesList).getByRole('button', { name: /^Page 2.*1 internal/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Add page' })).toBeInTheDocument();
    });

    it('selects a question on the canvas: its page, then the question', async () => {
        renderOutline();
        await tick();
        fireEvent.click(screen.getByRole('button', { name: 'Your city' }));
        expect(seen.slide.activeSlideComponent).toEqual({ id: 'p2', index: 1 });
        expect(seen.field.activeFieldComponent).toEqual({ id: 'city', index: 0 });
        expect(screen.getByRole('button', { name: 'Your city' })).toHaveAttribute('aria-current', 'true');
    });

    it('folds a page’s questions away', async () => {
        renderOutline();
        await tick();
        const toggle = screen.getByRole('button', { name: 'Questions on Page 2' });
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        fireEvent.click(toggle);
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByRole('button', { name: 'Your city' })).not.toBeInTheDocument();
    });

    it('reorders a question with the keyboard, across a page boundary, as one undo step', async () => {
        renderOutline();
        await tick();
        // email is last on p1; one step down passes p2's header: top of p2.
        await keyboardMove('Move question Your email', ['ArrowDown']);
        expect(fieldIds(0)).toEqual(['name']);
        expect(fieldIds(1)).toEqual(['email', 'city', 'ref']);
        expect(document.querySelector('[id^="DndLiveRegion"]')).toHaveTextContent(/Dropped question Your email at Page 2, position 1/);
        await act(async () => seen.builder.undo());
        expect(fieldIds(0)).toEqual(['name', 'email']);
    });

    it('reorders a page with the keyboard', async () => {
        renderOutline();
        await tick();
        // While a page moves its questions fold away: p3 is the next row below p2.
        await keyboardMove('Move Page 3', ['ArrowUp']);
        expect(seen.builder.formFields.map((s: StandardFormFieldDto) => s.id)).toEqual(['p1', 'p3', 'p2']);
    });

    it('moves a question from its menu and keeps focus on it', async () => {
        renderOutline();
        await tick();
        fireEvent.keyDown(screen.getByRole('button', { name: 'Options for question: Your name' }), { key: 'Enter' });
        await act(async () => fireEvent.click(await screen.findByRole('menuitem', { name: 'Move down' })));
        await tick();
        expect(fieldIds(0)).toEqual(['email', 'name']);
        expect(screen.getByRole('button', { name: /^Your name/ })).toHaveFocus();
        expect(document.getElementById('outline-announcer')).toHaveTextContent('Moved to About you, position 2 of 2.');
    });

    it('"Move to page" puts the question at the end of a folded page and unfolds it', async () => {
        renderOutline();
        await tick();
        fireEvent.click(screen.getByRole('button', { name: 'Questions on Page 2' }));
        fireEvent.keyDown(screen.getByRole('button', { name: 'Options for question: Your name' }), { key: 'Enter' });
        const sub = await screen.findByRole('menuitem', { name: 'Move to page…' });
        sub.focus();
        await act(async () => fireEvent.keyDown(sub, { key: 'ArrowRight' }));
        await act(async () => fireEvent.click(await screen.findByRole('menuitem', { name: /Page 2/ })));
        await tick();
        expect(fieldIds(1)).toEqual(['city', 'ref', 'name']);
        expect(screen.getByRole('button', { name: 'Questions on Page 2' })).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByRole('button', { name: /^Your name/ })).toHaveFocus();
    });

    it('moves a page from its menu', async () => {
        renderOutline();
        await tick();
        fireEvent.keyDown(screen.getByRole('button', { name: 'Options for Page 2' }), { key: 'Enter' });
        await act(async () => fireEvent.click(await screen.findByRole('menuitem', { name: 'Move up' })));
        expect(seen.builder.formFields.map((s: StandardFormFieldDto) => s.id)).toEqual(['p2', 'p1', 'p3']);
    });

    it('filters questions by title', async () => {
        renderOutline();
        await tick();
        fireEvent.change(screen.getByRole('searchbox', { name: 'Filter questions by title' }), { target: { value: 'CITY' } });
        expect(screen.getByRole('button', { name: 'Your city' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Your name' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /^About you/ })).not.toBeInTheDocument();
        expect(document.getElementById('outline-announcer')).toHaveTextContent('1 question match.');
    });

    it('makes each ending selectable, for the canvas and the properties panel', async () => {
        renderOutline();
        await tick();
        const endings = screen.getByRole('list', { name: 'Endings' });
        fireEvent.click(within(endings).getByRole('button', { name: /^Ending 2/ }));
        expect(seen.slide.activeSlideComponent).toEqual({ id: 'thank-you-page', index: -20 });
        expect(seen.ending.activeThankYouPageComponent.index).toBe(1);
        expect(within(endings).getByRole('button', { name: /^Ending 2/ })).toHaveAttribute('aria-current', 'true');
        expect(within(endings).getByRole('button', { name: /^Ending 1/ })).not.toHaveAttribute('aria-current');
        // The first ending is the default; no jump goes to the second yet.
        expect(within(endings).getByRole('button', { name: /^Ending 1.*Default/ })).toBeInTheDocument();
        expect(within(endings).getByRole('button', { name: /^Ending 2.*Not reached by any jump/ })).toBeInTheDocument();
        expect(screen.queryByText('Not shown to respondents')).not.toBeInTheDocument();
        fireEvent.click(within(endings).getByRole('button', { name: /^Ending 1/ }));
        expect(seen.ending.activeThankYouPageComponent.index).toBe(0);
    });

    const openEndingMenu = async (label: string, item: string | RegExp) => {
        fireEvent.keyDown(screen.getByRole('button', { name: `Options for ${label}` }), { key: 'Enter' });
        await act(async () => fireEvent.click(await screen.findByRole('menuitem', { name: item })));
    };
    const jumpTo = (endingId?: string) => ({ operator: 'AND', conditions: [{ fieldId: 'name', comparison: 'IS_EMPTY' }], target: '__SUBMIT__', ...(endingId ? { endingId } : {}) });

    it('a jump to an ending makes it reachable', async () => {
        renderOutline();
        await tick();
        act(() => seen.builder.updateSlideJumps(0, [jumpTo('ending-2')]));
        const endings = screen.getByRole('list', { name: 'Endings' });
        expect(within(endings).getByRole('button', { name: /^Ending 2/ })).not.toHaveTextContent('Not reached by any jump');
    });

    it('adds, renames and duplicates endings', async () => {
        renderOutline();
        await tick();
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Add ending' })));
        let endings = screen.getByRole('list', { name: 'Endings' });
        expect(within(endings).getAllByRole('listitem')).toHaveLength(3);
        // the new ending is selected, with a fresh id
        expect(seen.ending.activeThankYouPageComponent.index).toBe(2);
        const added = seen.endingState.formState.thankyouPage[2];
        expect(added.id).toMatch(/^[0-9a-f-]{36}$/);

        await openEndingMenu('Ending 2', 'Rename');
        const input = screen.getByRole('textbox', { name: /Ending name/ });
        fireEvent.change(input, { target: { value: 'Not eligible' } });
        fireEvent.keyDown(input, { key: 'Enter' });
        expect(seen.endingState.formState.thankyouPage[1].name).toBe('Not eligible');
        endings = screen.getByRole('list', { name: 'Endings' });
        expect(within(endings).getByRole('button', { name: /^Not eligible/ })).toBeInTheDocument();

        // Escape cancels a rename
        await openEndingMenu('Not eligible', 'Rename');
        fireEvent.change(screen.getByRole('textbox', { name: /Ending name/ }), { target: { value: 'Oops' } });
        fireEvent.keyDown(screen.getByRole('textbox', { name: /Ending name/ }), { key: 'Escape' });
        expect(seen.endingState.formState.thankyouPage[1].name).toBe('Not eligible');

        await openEndingMenu('Not eligible', 'Duplicate');
        const copy = seen.endingState.formState.thankyouPage[2];
        expect(copy.name).toBe('Not eligible (copy)');
        expect(copy.title).toBe('Sorry, not eligible');
        expect(copy.id).not.toBe(seen.endingState.formState.thankyouPage[1].id);
    });

    it('makes another ending the default', async () => {
        renderOutline();
        await tick();
        await openEndingMenu('Ending 2', 'Make default');
        expect(seen.endingState.formState.thankyouPage.map((e: any) => !!e.isDefault)).toEqual([false, true]);
        const endings = screen.getByRole('list', { name: 'Endings' });
        expect(within(endings).getByRole('button', { name: /^Ending 2.*Default/ })).toBeInTheDocument();
        // the first is now an ending no jump reaches
        expect(within(endings).getByRole('button', { name: /^Ending 1.*Not reached by any jump/ })).toBeInTheDocument();
    });

    it('deleting an ending sends its jumps to the default ending, and Undo brings both back', async () => {
        renderOutline();
        await tick();
        act(() => seen.builder.updateSlideJumps(0, [jumpTo('ending-2'), jumpTo()]));
        await openEndingMenu('Ending 2', 'Delete');
        expect(seen.endingState.formState.thankyouPage.map((e: any) => e.id)).toEqual(['ending-1']);
        // the jump still submits, now to the default ending
        expect(seen.builder.formFields[0].properties.jumps.map((j: any) => [j.target, j.endingId])).toEqual([
            ['__SUBMIT__', undefined],
            ['__SUBMIT__', undefined]
        ]);
        expect(await screen.findByText('Ending 2 deleted. 1 jump now shows the default ending.')).toBeInTheDocument();
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Undo' })));
        expect(seen.endingState.formState.thankyouPage.map((e: any) => e.id)).toEqual(['ending-1', 'ending-2']);
        expect(seen.builder.formFields[0].properties.jumps.map((j: any) => j.endingId)).toEqual(['ending-2', undefined]);
    });

    it('stops at 20 endings', async () => {
        renderOutline();
        await tick();
        act(() => seen.endingState.setFormState((prev: any) => ({ ...prev, thankyouPage: Array.from({ length: 20 }, (_, i) => ({ id: `e${i}` })) })));
        expect(screen.getByRole('button', { name: 'Add ending' })).toBeDisabled();
        fireEvent.keyDown(screen.getByRole('button', { name: 'Options for Ending 1' }), { key: 'Enter' });
        expect(await screen.findByRole('menuitem', { name: 'Duplicate' })).toHaveAttribute('aria-disabled', 'true');
    });

    const nextFrame = () => act(async () => new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0))));

    it('Rename from the keyboard puts focus in the name field; Escape cancels and goes back to the row', async () => {
        renderOutline();
        await tick();
        fireEvent.keyDown(screen.getByRole('button', { name: 'Options for Ending 2' }), { key: 'Enter' });
        const item = await screen.findByRole('menuitem', { name: 'Rename' });
        await act(async () => fireEvent.keyDown(item, { key: 'Enter' }));
        await nextFrame();
        const field = screen.getByRole('textbox', { name: /Ending name/ });
        expect(document.activeElement).toBe(field);
        fireEvent.change(field, { target: { value: 'Typed' } });
        await act(async () => fireEvent.keyDown(field, { key: 'Escape' }));
        await tick();
        expect(screen.queryByRole('textbox', { name: /Ending name/ })).not.toBeInTheDocument();
        expect(seen.endingState.formState.thankyouPage[1].name).toBeUndefined();
        expect(document.activeElement).toBe(within(screen.getByRole('list', { name: 'Endings' })).getByRole('button', { name: /^Ending 2/ }));
    });

    it('Rename with the mouse puts focus in the name field; Enter saves', async () => {
        renderOutline();
        await tick();
        const trigger = screen.getByRole('button', { name: 'Options for Ending 2' });
        fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: 'mouse' });
        await act(async () => fireEvent.click(await screen.findByRole('menuitem', { name: 'Rename' })));
        await nextFrame();
        const field = screen.getByRole('textbox', { name: /Ending name/ });
        expect(document.activeElement).toBe(field);
        fireEvent.change(field, { target: { value: 'Waiting list' } });
        await act(async () => fireEvent.keyDown(field, { key: 'Enter' }));
        expect(seen.endingState.formState.thankyouPage[1].name).toBe('Waiting list');
    });

    it('keeps at least one ending', async () => {
        renderOutline();
        await tick();
        await openEndingMenu('Ending 2', 'Delete');
        fireEvent.keyDown(screen.getByRole('button', { name: 'Options for Thank you' }), { key: 'Enter' });
        expect(await screen.findByRole('menuitem', { name: /Delete \(a form keeps one ending\)/ })).toHaveAttribute('aria-disabled', 'true');
    });
});
