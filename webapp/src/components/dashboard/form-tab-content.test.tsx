// The Pages view of a form: a grid of page cards sized from the grid they sit in (so the side menu and the page
// padding can change without the cards spilling out), and a note instead of an empty page for an imported form.
import React from 'react';

import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import { FormTabContent } from './form-tab-content';

vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@app/views/organism/form-preview/form-slide-preview', () => ({ default: () => <div /> }));
vi.mock('@app/views/organism/form/welcome-page', () => ({ default: () => <div /> }));
vi.mock('@app/views/organism/layout/layout-wrapper', () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

const form = { formId: 'f1', builderVersion: 'v2', welcomePage: {}, fields: [{ id: 's1', properties: { fields: [{ id: 'q1' }] } }] } as any;

const gridOf = (width: number) => vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(width);
const frameWidths = () => screen.getAllByRole('button', { name: /^Open preview at/ }).map((card) => (card.querySelector('span.aspect-video') as HTMLElement).style.width);

describe('the page cards', () => {
    afterEach(() => vi.restoreAllMocks());

    it("share the grid's width: two columns and a gap from lg, one column below", () => {
        const width = gridOf(1136);
        vi.stubGlobal('innerWidth', 1440);
        const { unmount } = render(<FormTabContent form={form} />);
        expect(frameWidths()).toEqual(['556px', '556px']);
        unmount();

        width.mockReturnValue(335);
        vi.stubGlobal('innerWidth', 375);
        render(<FormTabContent form={form} />);
        expect(frameWidths()).toEqual(['335px', '335px']);
        vi.unstubAllGlobals();
    });

    it('follow the grid when it changes size (the side menu collapsing)', () => {
        let observe: () => void = () => {};
        vi.stubGlobal(
            'ResizeObserver',
            class {
                constructor(callback: () => void) {
                    observe = callback;
                }
                observe() {}
                disconnect() {}
            }
        );
        const width = gridOf(1136);
        vi.stubGlobal('innerWidth', 1440);
        render(<FormTabContent form={form} />);
        expect(frameWidths()[0]).toBe('556px');
        width.mockReturnValue(1320);
        act(() => observe());
        expect(frameWidths()[0]).toBe('648px');
        vi.unstubAllGlobals();
    });
});

describe('a form imported from elsewhere', () => {
    it('says there are no page previews instead of showing an empty page', () => {
        render(<FormTabContent form={{ ...form, builderVersion: undefined }} />);
        expect(screen.getByTestId('pages-not-available')).toHaveTextContent('Page previews are only available for forms made here.');
        expect(screen.queryByRole('button')).toBeNull();
    });
});
