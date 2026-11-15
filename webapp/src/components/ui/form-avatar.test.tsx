import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { formHueIndex } from '@app/lib/form-hue';

import FormAvatar, { formHueClasses, formInitial } from './form-avatar';

afterEach(cleanup);

describe('a form tile', () => {
    it('keeps the same pair for the same id, whatever the case or the spaces around it', () => {
        const a = formHueClasses('64f1c0aa11bb22cc33dd44ee');
        expect(formHueClasses('64f1c0aa11bb22cc33dd44ee')).toBe(a);
        expect(formHueClasses('  64F1C0AA11BB22CC33DD44EE ')).toBe(a);
    });

    it('maps every hue index to its own tint and ink pair', () => {
        const pairs = new Set<string>();
        for (let seed = 0; pairs.size < 5 && seed < 500; seed++) pairs.add(formHueClasses(`form-${seed}`));
        expect([...pairs].sort()).toEqual([0, 1, 2, 3, 4].map((n) => `bg-form-hue-${n}-bg text-form-hue-${n}-ink`).sort());
    });

    it('is pinned: these ids get these pairs (changing the hash or the order recolours every form)', () => {
        const table = ['a', 'b', 'c', 'd', 'e', '64f1c0aa11bb22cc33dd44ee', 'form-1'].map((id) => [id, formHueIndex(id)]);
        expect(table.map(([id]) => formHueClasses(id as string))).toEqual(table.map(([, index]) => `bg-form-hue-${index}-bg text-form-hue-${index}-ink`));
    });

    it('shows the first letter of the title in capitals, else F, and hides itself from assistive technology', () => {
        const { rerender } = render(<FormAvatar formId="x1" title="  éclair survey" />);
        expect(screen.getByTestId('form-avatar')).toHaveTextContent('É');
        expect(screen.getByTestId('form-avatar')).toHaveAttribute('aria-hidden', 'true');
        rerender(<FormAvatar formId="x1" title="" />);
        expect(screen.getByTestId('form-avatar')).toHaveTextContent('F');
        expect(formInitial(undefined)).toBe('F');
        expect(formInitial('volunteer sign-up')).toBe('V');
    });

    it('takes its colours from the theme variables, never a hex or a ramp step', () => {
        const { container } = render(<FormAvatar formId="x1" title="Survey" />);
        expect(container.innerHTML).toMatch(/bg-form-hue-\d-bg text-form-hue-\d-ink/);
        expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,6}\b|\b(black|brand)-\d/i);
    });
});
