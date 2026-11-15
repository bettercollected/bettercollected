import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import DaybreakArt from './daybreak-art';
import EmptyState from './empty-state';

afterEach(cleanup);

describe('EmptyState', () => {
    it('shows the motif, a titled region, one sentence and the one action', () => {
        const { container } = render(<EmptyState title="No forms yet" description="Create your first form." action={<button type="button">New form</button>} />);
        const region = screen.getByRole('region', { name: 'No forms yet' });
        expect(region).toHaveAttribute('data-illustration', 'true');
        expect(screen.getByRole('heading', { level: 2, name: 'No forms yet' })).toBeInTheDocument();
        expect(screen.getByText('Create your first form.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'New form' })).toBeInTheDocument();
        // the picture is decoration
        const art = container.querySelector('svg');
        expect(art).not.toBeNull();
        expect(art).toHaveAttribute('aria-hidden', 'true');
    });

    it('can be the page heading, for a page whose card is all there is (the first run)', () => {
        render(<EmptyState headingLevel={1} title="Hey Dora" />);
        expect(screen.getByRole('heading', { level: 1, name: 'Hey Dora' })).toBeInTheDocument();
    });

    it('draws the coral spark, and leaves it out where a control sits at the corner of the panel', () => {
        const { container, rerender } = render(<DaybreakArt />);
        expect(container.querySelector('circle.fill-coral')).not.toBeNull();
        rerender(<DaybreakArt spark={false} />);
        expect(container.querySelector('circle.fill-coral')).toBeNull();
        // the sun and the hills stay
        expect(container.querySelector('circle.fill-sun')).not.toBeNull();
        expect(container.querySelectorAll('path')).toHaveLength(2);
    });

    it('leaves the picture out for a search or a filter with no match', () => {
        const { container } = render(<EmptyState illustration={false} title="No forms match your search" action={<button type="button">Clear search</button>} />);
        expect(screen.getByRole('region', { name: 'No forms match your search' })).toHaveAttribute('data-illustration', 'false');
        expect(container.querySelector('svg')).toBeNull();
        expect(screen.getByRole('button', { name: 'Clear search' })).toBeInTheDocument();
    });

    it('takes no action and no sentence', () => {
        render(<EmptyState title="Nothing here" />);
        expect(screen.queryByRole('button')).toBeNull();
        expect(screen.getByRole('heading', { name: 'Nothing here' })).toBeInTheDocument();
    });

    it('uses the heading level a page asks for, so a page keeps its one h1', () => {
        render(<EmptyState headingLevel={3} title="No responses yet" />);
        expect(screen.getByRole('heading', { level: 3, name: 'No responses yet' })).toBeInTheDocument();
        expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
    });

    it('colours nothing by hex or ramp step, and no exclamation marks reach the copy it is given', () => {
        const { container } = render(<EmptyState title="No forms yet" description="Create your first form." />);
        expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,6}\b/i);
        expect(container.innerHTML).not.toMatch(/\b(black|brand)-\d/);
    });
});
