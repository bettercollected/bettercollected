import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import FormProviderIcon from './form-provider-icon';

// Typeform is no longer integrated, but forms imported from it keep their
// provider and must still say where they came from.
describe('FormProviderIcon', () => {
    it('labels a form imported from Typeform without a brand logo', () => {
        const { container } = render(<FormProviderIcon provider="typeform" variant="full" size={24} />);
        expect(screen.getByText('Typeform')).toBeInTheDocument();
        expect(container.querySelector('svg')).not.toBeNull();
    });

    it('labels Google Forms and own forms as before', () => {
        render(<FormProviderIcon provider="google" variant="full" size={24} />);
        expect(screen.getByText('Google Forms')).toBeInTheDocument();
        render(<FormProviderIcon provider="self" variant="full" size={24} />);
        expect(screen.getByText('bettercollected')).toBeInTheDocument();
    });

    it('can show the icon alone', () => {
        render(<FormProviderIcon provider="typeform" variant="logo" size={24} />);
        expect(screen.queryByText('Typeform')).toBeNull();
    });
});
