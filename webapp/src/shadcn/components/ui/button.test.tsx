import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Button } from './button';

describe('Button', () => {
    it('gives the primary button the Sireto face and the key edge', () => {
        render(<Button>Save</Button>);
        const button = screen.getByRole('button', { name: 'Save' });
        expect(button.className).toContain('bg-action');
        expect(button.className).toContain('key-edge');
        expect(button.className).toContain('[--key-edge:var(--color-action-pressed)]');
        expect(button.className).toMatch(/(^|\s)rounded(\s|$)/);
    });

    it.each(['primary', 'secondary', 'tertiary', 'danger', 'v2Button'] as const)('%s has a key edge', (variant) => {
        render(<Button variant={variant}>Go</Button>);
        expect(screen.getByRole('button', { name: 'Go' }).className).toMatch(/(^|\s)key-edge(\s|$)/);
    });

    it.each(['ghost', 'dangerGhost', 'v2GhostButton'] as const)('%s has no face, so no edge', (variant) => {
        render(<Button variant={variant}>Go</Button>);
        expect(screen.getByRole('button', { name: 'Go' }).className).not.toMatch(/(^|\s)key-edge(\s|$)/);
    });

    it('drops the edge for flat (form-theme) buttons', () => {
        render(<Button flat>Submit response</Button>);
        expect(screen.getByRole('button', { name: 'Submit response' }).className).not.toMatch(/(^|\s)key-edge(\s|$)/);
    });

    it('leaves focus to the global outline rather than a per-variant ring', () => {
        render(<Button variant="tertiary">Go</Button>);
        expect(screen.getByRole('button', { name: 'Go' }).className).not.toMatch(/focus:ring/);
    });
});
