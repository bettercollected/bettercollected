import NavigationList from '@Components/sidebar/navigation-list';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { INavbarItem } from '@app/models/props/navbar';

import { CountBadge } from './count-badge';

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/dashboard/forms', useRouter: () => ({ push: vi.fn(), prefetch: vi.fn() }) }));

afterEach(cleanup);

describe('CountBadge', () => {
    it('is the number, named by the whole phrase', () => {
        render(<CountBadge count={2} label="2 waiting for you" />);
        const badge = screen.getByTestId('count-badge');
        // the number is drawn, but hidden from assistive technology: the phrase is what is read
        expect(badge.querySelector('[aria-hidden="true"]')).toHaveTextContent('2');
        expect(screen.getByText('2 waiting for you')).toHaveClass('sr-only');
        expect(badge).toHaveClass('bg-coral-tint', 'text-coral-ink');
    });

    it('renders nothing for zero', () => {
        const { container } = render(<CountBadge count={0} label="0 waiting for you" />);
        expect(container).toBeEmptyDOMElement();
    });

    it('caps a long count in the drawing, not in the phrase', () => {
        render(<CountBadge count={140} label="140 waiting for you" />);
        expect(screen.getByTestId('count-badge').querySelector('[aria-hidden="true"]')).toHaveTextContent('99+');
        expect(screen.getByText('140 waiting for you')).toBeInTheDocument();
    });
});

describe('a navigation item with something waiting', () => {
    const item = (badge?: INavbarItem['badge']): INavbarItem => ({ key: 'deletion_requests', name: 'Deletion requests', url: '/acme/dashboard/deletion-requests', badge });

    it('shows the badge next to its name, with an accessible phrase', () => {
        render(<NavigationList navigationList={[item({ count: 2, label: '2 waiting for you' })]} />);
        const row = screen.getByRole('listitem');
        expect(row).toHaveTextContent('Deletion requests');
        expect(screen.getByTestId('count-badge')).toBeInTheDocument();
        expect(screen.getByText('2 waiting for you')).toBeInTheDocument();
    });

    it('shows no badge when nothing is waiting', () => {
        render(<NavigationList navigationList={[item({ count: 0, label: '0 waiting for you' }), item()]} />);
        expect(screen.queryByTestId('count-badge')).toBeNull();
    });
});
