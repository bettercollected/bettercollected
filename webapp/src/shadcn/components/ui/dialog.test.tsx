import React from 'react';

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Dialog, DialogContent } from './dialog';

describe('the shared dialog\'s name', () => {
    it('is the hidden title for every dialog that does not opt in (nothing changed)', () => {
        render(
            <Dialog open>
                <DialogContent title="Invite someone">
                    <h2>A visible heading</h2>
                </DialogContent>
            </Dialog>
        );
        const dialog = screen.getByRole('dialog', { name: 'Invite someone' });
        const hidden = screen.getByText('Invite someone');
        // Radix links the dialog to its title; the title is not hidden from assistive technology
        expect(dialog.getAttribute('aria-labelledby')).toBe(hidden.id);
        expect(hidden).not.toHaveAttribute('aria-hidden');
        expect(hidden.className).toContain('sr-only');
    });

    it('is the default "Dialog" when no title is given', () => {
        render(
            <Dialog open>
                <DialogContent>
                    <p>text</p>
                </DialogContent>
            </Dialog>
        );
        expect(screen.getByRole('dialog', { name: 'Dialog' })).toBeInTheDocument();
    });

    it('can be a visible heading, by opt-in: the name is announced once and the hidden title steps aside', () => {
        render(
            <Dialog open>
                <DialogContent title="Your form is live" labelledBy="visible-title">
                    <h2 id="visible-title">Your form is live</h2>
                </DialogContent>
            </Dialog>
        );
        const dialog = screen.getByRole('dialog', { name: 'Your form is live' });
        expect(dialog.getAttribute('aria-labelledby')).toBe('visible-title');
        // one heading in the accessibility tree, not two
        expect(screen.getAllByRole('heading', { name: 'Your form is live' })).toHaveLength(1);
        // the hidden title is still in the markup (Radix asks for it) but not read
        const hidden = [...document.querySelectorAll('.sr-only')].find((element) => element.textContent === 'Your form is live');
        expect(hidden).toHaveAttribute('aria-hidden', 'true');
    });
});
