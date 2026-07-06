import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import TrustLayer from './trust-layer';

describe('TrustLayer — the privacy story on every form (Design-Language §4)', () => {
    it('names who is collecting the responses', () => {
        render(<TrustLayer ownerName="Acme Corp" />);
        expect(screen.getByText(/Collected by/)).toBeInTheDocument();
        expect(screen.getByText(/Acme Corp/)).toBeInTheDocument();
    });

    it('links to the privacy policy only when a URL exists', () => {
        const { rerender } = render(<TrustLayer ownerName="Acme" privacyUrl="https://acme.test/privacy" />);
        const link = screen.getByRole('link', { name: /how your data is used/i });
        expect(link).toHaveAttribute('href', 'https://acme.test/privacy');

        rerender(<TrustLayer ownerName="Acme" />);
        expect(screen.queryByRole('link', { name: /how your data is used/i })).not.toBeInTheDocument();
    });

    it('always states the right to view or delete the response', () => {
        render(<TrustLayer ownerName="Acme" />);
        expect(screen.getByText(/view or delete your response/i)).toBeInTheDocument();
    });

    it('shows purpose and retention when provided', () => {
        render(<TrustLayer ownerName="Acme" purpose="To schedule your appointment" retention="kept for 90 days" />);
        expect(screen.getByText(/schedule your appointment/i)).toBeInTheDocument();
        expect(screen.getByText(/kept for 90 days/i)).toBeInTheDocument();
    });
});
