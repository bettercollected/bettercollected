import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import FormPublishedModal from './form-publised-modal';

const renderModal = (appTheme = 'daybreak') => {
    (window as any).PUBLIC_CONFIG = { HTTP_SCHEME: 'https://', FORM_DOMAIN: 'forms.example.test', DASHBOARD_DOMAIN: 'admin.example.test' };
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', appTheme } as any));
    store.dispatch(setForm({ formId: 'f-123', builderVersion: 'v2', settings: {} } as any));
    return render(
        <ReduxProvider store={store}>
            <FormPublishedModal />
        </ReduxProvider>
    );
};

describe('the published dialog', () => {
    let writeText: ReturnType<typeof vi.fn>;
    beforeEach(() => {
        writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    });
    afterEach(() => vi.useRealTimers());

    it("draws Pigment's flat shapes when the workspace is in Pigment (the dialog is portalled out of the scope, so the store tells), and the sun and hills otherwise", () => {
        const { container, unmount } = renderModal('pigment');
        expect(screen.getByTestId('pigment-app-art')).toHaveAttribute('data-variant', 'panel');
        expect(container.querySelector('circle.fill-sun')).toBeNull();
        // no ring beside the close button, as no coral dot in Daybreak
        expect([...screen.getByTestId('pigment-app-art').querySelectorAll('circle')].some((c) => c.getAttribute('fill') === 'none')).toBe(false);
        expect(screen.getByTestId('published-mark').parentElement?.className).toContain('bg-sunken');
        unmount();
        {
            const view = renderModal('daybreak');
            expect(screen.queryByTestId('pigment-app-art')).toBeNull();
            expect(view.container.querySelector('circle.fill-sun')).not.toBeNull();
            expect(view.container.querySelector('circle.fill-coral')).toBeNull(); // spark off in this dialog, as before
            expect(screen.getByTestId('published-mark').parentElement?.className).toBe('relative h-[96px] bg-brand-tint sm:h-[112px]');
            view.unmount();
        }
    });

    it('says the form is live with a mark that is a shape, and shows the link in full view', () => {
        renderModal();
        expect(screen.getByRole('heading', { name: 'Your form is live' })).toBeInTheDocument();
        // the check is drawn, hidden from assistive technology (the heading says it)
        const mark = screen.getByTestId('published-mark');
        expect(mark.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
        expect(screen.getByTestId('published-link')).toHaveTextContent('https://forms.example.test/acme/forms/f-123');
    });

    it('wears the motif once, hidden from assistive technology', () => {
        const { container } = renderModal();
        const art = container.querySelectorAll('svg[viewBox="-360 0 1000 148"]');
        expect(art).toHaveLength(1);
        expect(art[0]).toHaveAttribute('aria-hidden', 'true');
        // no coral dot beside the dialog's close button: it would read as a notification
        expect(container.querySelector('circle.fill-coral')).toBeNull();
    });

    it('settles the check once and only for people who have not asked for less motion', () => {
        renderModal();
        const classes = screen.getByTestId('published-mark').className.split(/\s+/);
        const animated = classes.filter((name) => /animate-in|zoom-in|fade-in/.test(name));
        expect(animated.length).toBeGreaterThan(0);
        for (const name of animated) expect(name.startsWith('motion-safe:')).toBe(true);
        // no looping animation anywhere in the dialog
        expect(document.body.innerHTML).not.toMatch(/animate-(spin|pulse|bounce|ping)/);
    });

    it('copies the link and says so in a status line a screen reader announces', async () => {
        renderModal();
        const status = screen.getByRole('status');
        // the live region is in the page before anything is copied, and empty
        expect(status).toBeEmptyDOMElement();
        fireEvent.click(screen.getByRole('button', { name: 'Copy link' }));
        await waitFor(() => expect(status).toHaveTextContent('Link copied to clipboard'));
        expect(writeText).toHaveBeenCalledWith('https://forms.example.test/acme/forms/f-123');
        expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
    });

    it('says plainly when the browser would not copy, and that the link can be copied by hand', async () => {
        writeText.mockRejectedValue(new Error('denied'));
        renderModal();
        fireEvent.click(screen.getByRole('button', { name: 'Copy link' }));
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Could not copy. Select the link and copy it yourself.'));
        expect(screen.getByRole('button', { name: 'Copy link' })).toBeInTheDocument();
    });

    it('keeps the two buttons where they are whatever the status says: the status line is reserved under them, not in the rows above', async () => {
        renderModal();
        const status = screen.getByTestId('published-copy-status');
        const open = screen.getByRole('link', { name: /Open the form/ });
        const buttons = open.parentElement as HTMLElement;
        const linkRow = screen.getByTestId('published-link').closest('.sm\\:flex-row') as HTMLElement;
        // nothing above the buttons holds the status, so its text cannot push them down
        expect(linkRow).not.toContainElement(status);
        expect(buttons).not.toContainElement(status);
        // it comes after the buttons in the same column, with its own line reserved whether or not it has text, and is always in the page
        expect(buttons.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(status.parentElement).toBe(buttons.parentElement);
        expect(status.className).toContain('min-h-5');
        expect(status.className).not.toMatch(/sr-only|hidden/);
        // the status line sits inside the dialog's own padding: the bottom matches the sides (24 px, 32 px from sm)
        expect(status.parentElement!.className).toMatch(/\bp-6\b.*\bpb-6\b.*\bsm:p-8\b.*\bsm:pb-8\b/);
        const before = Array.from(buttons.parentElement!.children).indexOf(buttons);
        fireEvent.click(screen.getByRole('button', { name: /Copy link/ }));
        await waitFor(() => expect(status).toHaveTextContent('Link copied to clipboard'));
        expect(Array.from(buttons.parentElement!.children).indexOf(buttons)).toBe(before);
        expect(status.className).toContain('min-h-5');
    });

    it('clears the status line again', async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        renderModal();
        fireEvent.click(screen.getByRole('button', { name: 'Copy link' }));
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Link copied'));
        await act(async () => {
            await vi.advanceTimersByTimeAsync(3100);
        });
        expect(screen.getByRole('status')).toBeEmptyDOMElement();
        expect(screen.getByRole('button', { name: 'Copy link' })).toBeInTheDocument();
    });

    it('offers two next steps as links with names: open the form (a new tab, said aloud) and more ways to share', () => {
        renderModal();
        const open = screen.getByRole('link', { name: /^Open the form\s*\(opens in a new tab\)$/ });
        expect(open).toHaveAttribute('href', 'https://forms.example.test/acme/forms/f-123');
        expect(open).toHaveAttribute('target', '_blank');
        expect(open).toHaveAttribute('rel', expect.stringContaining('noopener'));
        const more = screen.getByRole('link', { name: 'More ways to share' });
        expect(more).toHaveAttribute('href', 'https://admin.example.test/acme/dashboard/forms/f-123?view=FormLinks');
    });

    it('keeps the order: the Copy button is the first control, then the two links', () => {
        const { container } = renderModal();
        const controls = [...container.querySelectorAll('button, a[href]')].map((element) => element.textContent?.trim());
        expect(controls[0]).toBe('Copy link');
        expect(controls[1]).toContain('Open the form');
        expect(controls[2]).toBe('More ways to share');
    });

    it('colours nothing by hand outside the shared buttons: no hex and no ramp steps', () => {
        const { container } = renderModal();
        // the buttons carry the app's own variants; everything this dialog adds is semantic
        const own = container.cloneNode(true) as HTMLElement;
        own.querySelectorAll('button, a').forEach((element) => element.remove());
        const html = own.innerHTML;
        expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
        expect(html).not.toMatch(/(?:bg|text|border|fill|ring)-(?:black|brand|gray|red|green)-\d/);
        expect(within(container).getByRole('heading').className).toContain('text-ink');
    });
});
