import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';

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
    const { setFormState } = useFormState();
    Object.assign(seen, { builder, slide, field, ending });
    React.useEffect(() => {
        builder.initFormFields(pages());
        setFormState((prev) => ({ ...prev, thankyouPage: [{ title: 'Thanks!' }, { title: 'Sorry, not eligible' }] }));
    }, []);
    return <LeftDrawer formFields={builder.formFields} activeSlideComponent={slide.activeSlideComponent} />;
}

const renderOutline = () =>
    render(
        <Provider>
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
        // Only the first ending reaches respondents today; the outline says so.
        expect(within(endings).getByRole('button', { name: /^Ending 2.*Not shown to respondents/ })).toBeInTheDocument();
        fireEvent.click(within(endings).getByRole('button', { name: /^Ending 1/ }));
        expect(seen.ending.activeThankYouPageComponent.index).toBe(0);
    });
});
