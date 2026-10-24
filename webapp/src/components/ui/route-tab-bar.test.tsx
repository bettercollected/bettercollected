// The shared tab bar for tabs that are pages (Members, Single sign-on, AI).
import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { axeViolations } from '@app/test/axe';

import RouteTabBar, { RouteTab } from './route-tab-bar';

let pathname = '/acme/dashboard/sso';
vi.mock('next/navigation', () => ({ usePathname: () => pathname }));

const TABS: Array<RouteTab> = [
    { key: 'sso', label: 'Single sign-on', href: '/acme/dashboard/sso', exact: true },
    { key: 'domains', label: 'Domains', href: '/acme/dashboard/sso/domains' }
];

const renderBar = (tabs = TABS) => render(<RouteTabBar ariaLabel="Single sign-on sections" tabs={tabs} />);

describe('RouteTabBar', () => {
    beforeEach(() => {
        pathname = '/acme/dashboard/sso';
    });

    it('is a named nav of links, not a tablist', () => {
        renderBar();
        const nav = screen.getByRole('navigation', { name: 'Single sign-on sections' });
        const links = within(nav).getAllByRole('link');
        expect(links.map((link) => link.getAttribute('href'))).toEqual(['/acme/dashboard/sso', '/acme/dashboard/sso/domains']);
        expect(screen.queryByRole('tablist')).toBeNull();
        expect(screen.queryByRole('tab')).toBeNull();
    });

    it('marks the current tab with aria-current="page", and only that one', () => {
        renderBar();
        expect(screen.getByRole('link', { name: 'Single sign-on' })).toHaveAttribute('aria-current', 'page');
        expect(screen.getByRole('link', { name: 'Domains' })).not.toHaveAttribute('aria-current');
    });

    it('does not mark a tab whose path only prefixes the current one', () => {
        pathname = '/acme/dashboard/sso/domains';
        renderBar();
        expect(screen.getByRole('link', { name: 'Domains' })).toHaveAttribute('aria-current', 'page');
        expect(screen.getByRole('link', { name: 'Single sign-on' })).not.toHaveAttribute('aria-current');
    });

    it('shows the active tab by weight and underline, not colour alone', () => {
        renderBar();
        expect(screen.getByRole('link', { name: 'Single sign-on' })).toHaveClass('font-semibold', 'border-brand-500');
        expect(screen.getByRole('link', { name: 'Domains' })).toHaveClass('font-medium', 'border-transparent');
    });

    it('gives every tab a 44px touch target and a visible focus ring', () => {
        renderBar();
        for (const link of screen.getAllByRole('link')) {
            expect(link).toHaveClass('min-h-[44px]', 'focus-visible:outline-offset-[-2px]!');
        }
    });

    it('scrolls inside its own region', () => {
        renderBar();
        expect(screen.getByRole('list')).toHaveClass('overflow-x-auto');
    });

    it('renders nothing for a single tab', () => {
        const { container } = renderBar([TABS[1]]);
        expect(container).toBeEmptyDOMElement();
    });

    it('has no axe violations', async () => {
        const { container } = renderBar();
        expect(await axeViolations(container)).toEqual([]);
    });
});
