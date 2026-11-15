import React from 'react';

import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DELETION_TABLE_PADDING, deletionRequestColumnLayout, withDeletionRequestLayout } from './deletion-request-columns';
import { deletionRequestTableStyles } from './datatable-styles';
import ScrollTable, { ScrollRegion } from './scroll-table';

describe('the scroll region of a table', () => {
    afterEach(() => vi.restoreAllMocks());

    it('is a named region a keyboard can focus', () => {
        render(
            <ScrollRegion label="Collaborators">
                <p>table</p>
            </ScrollRegion>
        );
        const region = screen.getByRole('region', { name: 'Collaborators' });
        expect(region).toHaveAttribute('tabindex', '0');
        expect(region.className).toContain('overflow-x-auto');
    });

    it('fades the edge that has more behind it, from the scroll position, and only then', () => {
        const { container } = render(
            <ScrollRegion label="Members">
                <p>table</p>
            </ScrollRegion>
        );
        const region = screen.getByRole('region', { name: 'Members' });
        const fade = (side: string) => container.querySelector(`[data-fade="${side}"]`)!.getAttribute('data-more');
        // nothing to scroll
        expect(fade('start')).toBe('false');
        expect(fade('end')).toBe('false');
        // wider than the card, at the start: more on the right
        Object.defineProperty(region, 'clientWidth', { configurable: true, value: 300 });
        Object.defineProperty(region, 'scrollWidth', { configurable: true, value: 900 });
        act(() => {
            region.dispatchEvent(new Event('scroll'));
        });
        expect(fade('start')).toBe('false');
        expect(fade('end')).toBe('true');
        // scrolled to the middle: both; to the end: only the left
        region.scrollLeft = 200;
        act(() => {
            region.dispatchEvent(new Event('scroll'));
        });
        expect(fade('start')).toBe('true');
        expect(fade('end')).toBe('true');
        region.scrollLeft = 600;
        act(() => {
            region.dispatchEvent(new Event('scroll'));
        });
        expect(fade('start')).toBe('true');
        expect(fade('end')).toBe('false');
        // the fades are decorative, in the strong hairline colour
        const fades = container.querySelectorAll('[data-fade]');
        fades.forEach((element) => {
            expect(element.getAttribute('aria-hidden')).toBe('true');
            expect(element.className).toContain('from-hairline-strong');
            expect(element.className).toContain('pointer-events-none');
        });
    });

    it('wraps the app table: its own scroll box is off so the region scrolls', () => {
        // react-data-table asks for the colour scheme
        window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {} }) as any;
        render(<ScrollTable label="Groups" columns={[{ name: 'Group', selector: (row: { name: string }) => row.name }]} data={[{ name: 'Buurtbewoners' }]} />);
        const region = screen.getByRole('region', { name: 'Groups' });
        expect(region.querySelector('.rdt_responsiveWrapperScroll')).toBeNull();
        expect(screen.getByText('Buurtbewoners')).toBeInTheDocument();
    });
});

// The deletion requests table (the workspace's page and a form's): every column says what it needs and who gets the
// rest, the smallest the table gets fits a 1440 px card, and the header and the cells share one left padding.
describe('the deletion requests table columns', () => {
    const MIN_SUM = (withForm: boolean) => deletionRequestColumnLayout(withForm).reduce((sum, column) => sum + parseInt(column.minWidth, 10), 0);

    it('fit the card at 1440 (main 1151 px, a card of 1070, 1068 inside its border) with and without the form column', () => {
        expect(MIN_SUM(true)).toBeLessThanOrEqual(1068);
        expect(MIN_SUM(false)).toBeLessThanOrEqual(1068);
    });

    it('give the address and the form name the room that is left, and let a date wrap instead of being cut', () => {
        const [by, form, on, status, deleted, actions] = deletionRequestColumnLayout(true);
        expect(by.grow).toBeGreaterThan(on.grow);
        expect(form.grow).toBeGreaterThan(status.grow);
        // every text column may wrap: a nowrap cell would put its whole text back into the table's fit-content width
        for (const column of [by, form, on, deleted]) expect(column.wrap).toBe(true);
        expect(parseInt(on.minWidth, 10)).toBeGreaterThanOrEqual(200);
        // the action column keeps View and Delete response side by side and takes no more
        expect(parseInt(actions.minWidth, 10)).toBeGreaterThanOrEqual(180);
        expect(actions.grow).toBe(0);
    });

    it('apply to the columns in order, with one left padding that the header shares', () => {
        const columns = [{ name: 'a', style: { paddingLeft: '8px', color: 'x' } }, { name: 'b' }, { name: 'c' }, { name: 'd' }, { name: 'e' }];
        const laid = withDeletionRequestLayout(columns, false);
        expect(laid).toHaveLength(5);
        expect(laid[0]).toMatchObject({ name: 'a', minWidth: '225px', grow: 2, style: { paddingLeft: DELETION_TABLE_PADDING, color: 'x' } });
        expect(laid.every((column) => column.style.paddingLeft === DELETION_TABLE_PADDING)).toBe(true);
        expect(deletionRequestTableStyles.headCells.style.paddingLeft).toBe(DELETION_TABLE_PADDING);
    });
});
