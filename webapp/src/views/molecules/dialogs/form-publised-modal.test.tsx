import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import FormPublishedModal from './form-publised-modal';

const renderModal = () => {
    (window as any).PUBLIC_CONFIG = { HTTP_SCHEME: 'https://', FORM_DOMAIN: 'forms.example.test', DASHBOARD_DOMAIN: 'admin.example.test' };
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
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
