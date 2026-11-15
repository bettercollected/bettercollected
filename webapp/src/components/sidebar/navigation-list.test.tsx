// The workspace sidebar's rows are real controls: links where an item is a page, buttons where it acts in place,
// in DOM order, with the current page announced.
import React from 'react';

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { INavbarItem } from '@app/models/props/navbar';

import NavigationList from './navigation-list';

let pathname = '/acme/dashboard/forms';
const push = vi.fn();
const prefetch = vi.fn();
vi.mock('next/navigation', () => ({ usePathname: () => pathname, useRouter: () => ({ push, prefetch }) }));

const onSettings = vi.fn();
const onSite = vi.fn();

const items = (): Array<INavbarItem> => [
    { key: 'forms', name: 'Forms', url: '/acme/dashboard/forms', icon: <svg data-testid="icon" aria-hidden="true" /> },
    { key: 'deletion', name: 'Deletion requests', url: '/acme/dashboard/deletion-requests', badge: { count: 2, label: '2 waiting for you' } },
    { key: 'site', name: 'Site', url: '/acme/dashboard', exactMatch: true, isActive: false, onClick: onSite },
    { key: 'site-settings', name: 'Site settings', url: '/acme/dashboard/site-settings', isActive: false, opensInPlace: true, onClick: onSettings }
];

beforeEach(() => {
    pathname = '/acme/dashboard/forms';
    push.mockClear();
    prefetch.mockClear();
    onSettings.mockClear();
    onSite.mockClear();
});
afterEach(cleanup);

describe('the sidebar rows', () => {
    it('are links or buttons, one per item, in the order of the list, named by the item', () => {
        render(<NavigationList navigationList={items()} />);
        const focusable = Array.from(document.querySelectorAll<HTMLElement>('a[href], button, [tabindex]'));
        expect(focusable.map((el) => el.tagName)).toEqual(['A', 'A', 'A', 'BUTTON']);
        expect(focusable.some((el) => el.getAttribute('tabindex') === '-1')).toBe(false);
        expect(screen.getByRole('link', { name: 'Forms' })).toBeInTheDocument();
        // the badge's phrase is part of the name, the drawn number is hidden
        expect(screen.getByRole('link', { name: /^Deletion requests\s*2 waiting for you$/ })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Site' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Site settings' })).toBeInTheDocument();
    });

    it('keep the list: one listitem per row, none of them clickable itself', () => {
        render(<NavigationList navigationList={items()} />);
        const rows = screen.getAllByRole('listitem');
        expect(rows).toHaveLength(4);
        rows.forEach((row) => {
            fireEvent.click(row);
        });
        expect(push).not.toHaveBeenCalled();
        expect(onSite).not.toHaveBeenCalled();
        expect(onSettings).not.toHaveBeenCalled();
    });

    it('mark only the current page with aria-current', () => {
        render(<NavigationList navigationList={items()} />);
        const links = screen.getAllByRole('link');
        expect(links.filter((link) => link.getAttribute('aria-current') === 'page').map((link) => link.textContent)).toEqual(['Forms']);
        expect(screen.getByRole('button', { name: 'Site settings' })).not.toHaveAttribute('aria-current');
    });

    it('mark an item that is active by a flag, the nested route, and an open view', () => {
        pathname = '/acme/dashboard/deletion-requests/123';
        const list = items().map((item) => (item.key === 'site-settings' ? { ...item, isActive: true } : item));
        render(<NavigationList navigationList={list} />);
        expect(screen.getByRole('link', { name: /Deletion requests/ })).toHaveAttribute('aria-current', 'page');
        expect(screen.getByRole('link', { name: 'Forms' })).not.toHaveAttribute('aria-current');
        expect(screen.getByRole('button', { name: 'Site settings' })).toHaveAttribute('aria-current', 'true');
    });

    it('carry the url as the href, so Enter follows it and it opens in a new tab', () => {
        render(<NavigationList navigationList={items()} />);
        expect(screen.getByRole('link', { name: 'Forms' })).toHaveAttribute('href', '/acme/dashboard/forms');
        expect(screen.getByRole('link', { name: 'Site' })).toHaveAttribute('href', '/acme/dashboard');
    });

    it('prefetch each url once, as before', () => {
        render(<NavigationList navigationList={items()} />);
        expect(prefetch.mock.calls.map((call) => call[0])).toEqual(['/acme/dashboard/forms', '/acme/dashboard/deletion-requests', '/acme/dashboard', '/acme/dashboard/site-settings']);
    });

    it('run the action of a link item on a plain click, and leave a new-tab click to the browser', () => {
        render(<NavigationList navigationList={items()} />);
        const site = screen.getByRole('link', { name: 'Site' });
        expect(fireEvent.click(site)).toBe(false); // default prevented: the action replaces the navigation
        expect(onSite).toHaveBeenCalledTimes(1);
        expect(fireEvent.click(site, { ctrlKey: true })).toBe(true);
        expect(fireEvent.click(site, { metaKey: true })).toBe(true);
        expect(onSite).toHaveBeenCalledTimes(1);
    });

    it('make an in-place item a native button of type button that runs its action once', () => {
        render(<NavigationList navigationList={items()} />);
        const button = screen.getByRole('button', { name: 'Site settings' });
        // a native button: Enter and Space activate it in the browser
        expect(button.tagName).toBe('BUTTON');
        expect(button).toHaveAttribute('type', 'button');
        expect(button).not.toHaveAttribute('href');
        fireEvent.click(button);
        expect(onSettings).toHaveBeenCalledTimes(1);
    });

    it('draw the same box on a link and on a button', () => {
        render(<NavigationList navigationList={items()} />);
        const link = screen.getByRole('link', { name: 'Forms' });
        const button = screen.getByRole('button', { name: 'Site settings' });
        const box = ['flex', 'w-full', 'items-center', 'px-4', 'py-2', 'cursor-pointer', 'rounded-lg', 'text-sm', 'transition-colors'];
        expect(link).toHaveClass(...box, 'bg-brand-tint', 'text-link', 'font-medium');
        expect(button).toHaveClass(...box, 'text-copy', 'hover:bg-sunken', 'hover:text-ink', 'text-start');
    });

    it('have no list item or div that is clickable without a role', () => {
        const { container } = render(<NavigationList navigationList={items()} />);
        // React puts no onclick attribute in the DOM, so the tree is checked instead: each li holds exactly one
        // link or button (the only clickable element), and no div in the list is a click target of its own.
        container.querySelectorAll('li').forEach((li) => {
            expect(li.children).toHaveLength(1);
            expect(['A', 'BUTTON']).toContain(li.children[0].tagName);
        });
        expect(container.querySelectorAll('ul > div, li div[tabindex], li div[role]')).toHaveLength(0);
    });
});
