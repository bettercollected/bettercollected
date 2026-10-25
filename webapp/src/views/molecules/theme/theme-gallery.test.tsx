// The builder's theme gallery and the contrast guard of the theme editors.
import { useState } from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';
import { themeContrastGuard } from '@app/utils/theme-contrast';

import ThemeContrastGuard from './theme-contrast-guard';
import ThemeGallery, { ThemeGallerySection } from './theme-gallery';

const PALE: FormTheme = { title: 'Pastel', primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' };

const sections: ThemeGallerySection[] = [
    { key: 'saved', label: 'Your themes', entries: [{ value: 'saved:Pastel', label: 'Pastel', theme: PALE }] },
    { key: 'presets', label: 'Presets', entries: ThemeColors.slice(0, 3).map((theme) => ({ value: `preset:${theme.title}`, label: theme.title, theme })) },
    { key: 'custom', label: 'One-off', entries: [{ value: 'custom', label: 'Custom colours', theme: ThemeColors[0] }] }
];

const Gallery = ({ onSelect }: { onSelect?: (value: string) => void }) => {
    const [value, setValue] = useState('preset:Default');
    return (
        <ThemeGallery
            sections={sections}
            value={value}
            sample={{ question: 'What is your name?', answer: 'Ada' }}
            onSelect={(next) => {
                onSelect?.(next);
                setValue(next);
            }}
        />
    );
};

describe('the theme gallery', () => {
    it('is one radio group: Tab reaches the chosen theme, arrows move and choose', () => {
        const onSelect = vi.fn();
        render(<Gallery onSelect={onSelect} />);
        const group = screen.getByRole('radiogroup', { name: 'Theme' });
        const radios = within(group).getAllByRole('radio');
        expect(radios).toHaveLength(5);
        const chosen = within(group).getByRole('radio', { checked: true });
        expect(chosen).toHaveAccessibleName('Default');
        expect(radios.filter((radio) => radio.tabIndex === 0)).toEqual([chosen]);

        chosen.focus();
        fireEvent.keyDown(chosen, { key: 'ArrowRight' });
        expect(onSelect).toHaveBeenLastCalledWith(`preset:${ThemeColors[1].title}`);
        expect(document.activeElement).toBe(within(group).getByRole('radio', { name: ThemeColors[1].title }));
        expect(within(group).getByRole('radio', { name: ThemeColors[1].title })).toHaveAttribute('aria-checked', 'true');

        fireEvent.keyDown(document.activeElement!, { key: 'End' });
        expect(onSelect).toHaveBeenLastCalledWith('custom');
        fireEvent.keyDown(document.activeElement!, { key: 'ArrowRight' });
        // wraps to the first card
        expect(onSelect).toHaveBeenLastCalledWith('saved:Pastel');
    });

    it('chooses with a click, and says in words which theme is hard to read', () => {
        const onSelect = vi.fn();
        render(<Gallery onSelect={onSelect} />);
        const pastel = screen.getByRole('radio', { name: 'Pastel' });
        expect(pastel).toHaveAccessibleDescription('Hard to read');
        expect(screen.getByRole('radio', { name: 'Default' })).not.toHaveAccessibleDescription();
        fireEvent.click(pastel);
        expect(onSelect).toHaveBeenLastCalledWith('saved:Pastel');
        expect(screen.getAllByText('Hard to read')).toHaveLength(1);
    });

    it('shows each theme on the form’s own first question', () => {
        render(<Gallery />);
        expect(screen.getAllByText('What is your name?')).toHaveLength(5);
        expect(screen.getAllByText('Ada')).toHaveLength(5);
    });

    it('has no WCAG A/AA violations', async () => {
        const { container } = render(<Gallery />);
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('the contrast guard', () => {
    it('says a passing theme passes', () => {
        render(<ThemeContrastGuard theme={ThemeColors[0]} />);
        expect(screen.getByTestId('contrast-guard')).toHaveTextContent('Readable: text reaches 4.5:1 and controls 3:1');
    });

    it('lists every failing pair with its ratio, and applies the suggested colours in one click', () => {
        const onApplyFix = vi.fn();
        render(<ThemeContrastGuard theme={PALE} onApplyFix={onApplyFix} />);
        const guard = screen.getByTestId('contrast-guard');
        expect(guard).toHaveTextContent('5 colour pairs are hard to read. Fix them before you save or publish this theme.');
        expect(guard).toHaveTextContent('Questions and text on the page: 2.5:1, needs 4.5:1');
        expect(guard).toHaveTextContent('Input borders on the page: 1.2:1, needs 3.0:1');
        fireEvent.click(screen.getByRole('button', { name: 'Use the suggested colours' }));
        const fixed = onApplyFix.mock.calls[0][0] as FormTheme;
        expect(fixed.title).toBe('Pastel');
        expect(themeContrastGuard(fixed).issues).toEqual([]);
    });

    it('never rounds a failing ratio up to its minimum', () => {
        // #777777 on white is 4.48:1: shown as 4.4, not 4.5
        render(<ThemeContrastGuard theme={{ ...ThemeColors[0], primary: '#777777', accent: '#FFFFFF' }} />);
        expect(screen.getByTestId('contrast-guard')).toHaveTextContent('4.4:1, needs 4.5:1');
    });

    it('is honest about an image it cannot measure', () => {
        render(<ThemeContrastGuard theme={{ ...ThemeColors[0], background: { type: 'image', imageUrl: '/a.png' } }} />);
        expect(screen.getByTestId('contrast-guard')).toHaveTextContent("Text over an image can't be measured.");
    });

    it('has no WCAG A/AA violations', async () => {
        const { container } = render(<ThemeContrastGuard theme={PALE} onApplyFix={vi.fn()} />);
        expect(await axeViolations(container)).toEqual([]);
    });
});
