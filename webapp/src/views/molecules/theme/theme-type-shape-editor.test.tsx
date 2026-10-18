import { useState } from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import '@app/shared/hocs/i18n-provider';

import ThemeTypeShapeEditor from './theme-type-shape-editor';

describe('the type and shape editor', () => {
    const base: FormTheme = { ...ThemeColors[0] };

    it('sets and clears corners, buttons and highlight with buttons a keyboard reaches', () => {
        const onChange = vi.fn();
        const { rerender } = render(<ThemeTypeShapeEditor theme={base} onChange={onChange} />);
        const sharp = screen.getByRole('button', { name: 'Sharp' });
        sharp.focus();
        expect(document.activeElement).toBe(sharp);
        fireEvent.click(sharp);
        expect(onChange).toHaveBeenLastCalledWith({ ...base, radius: 'sharp' });
        expect(screen.getByRole('button', { name: 'Default' })).toHaveAttribute('aria-pressed', 'true');

        rerender(<ThemeTypeShapeEditor theme={{ ...base, radius: 'sharp', buttonStyle: 'outlined' }} onChange={onChange} />);
        expect(screen.getByRole('button', { name: 'Sharp' })).toHaveAttribute('aria-pressed', 'true');
        fireEvent.click(screen.getByRole('button', { name: 'Default' }));
        // the default removes the key: no key, the look forms had before
        expect(onChange).toHaveBeenLastCalledWith({ ...base, buttonStyle: 'outlined' });
        fireEvent.click(screen.getByRole('button', { name: 'Filled' }));
        expect(onChange).toHaveBeenLastCalledWith({ ...base, radius: 'sharp' });

        fireEvent.click(screen.getByRole('button', { name: 'Add a highlight' }));
        expect(onChange).toHaveBeenLastCalledWith({ ...base, radius: 'sharp', buttonStyle: 'outlined', highlight: '#1649E2' });
        rerender(<ThemeTypeShapeEditor theme={{ ...base, highlight: '#A3305A' }} onChange={onChange} />);
        fireEvent.click(screen.getByRole('button', { name: 'Remove highlight' }));
        expect(onChange).toHaveBeenLastCalledWith(base);
    });

    it('keeps keyboard focus on the highlight controls when they swap', () => {
        const Editor = () => {
            const [theme, setTheme] = useState<FormTheme>(base);
            return <ThemeTypeShapeEditor theme={theme} onChange={setTheme} />;
        };
        render(<Editor />);
        const add = screen.getByRole('button', { name: 'Add a highlight' });
        add.focus();
        fireEvent.click(add);
        // the colour input replaces the button and takes focus
        const colour = screen.getByLabelText('Highlight');
        expect(colour).toHaveAttribute('type', 'color');
        expect(document.activeElement).toBe(colour);
        fireEvent.click(screen.getByRole('button', { name: 'Remove highlight' }));
        expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Add a highlight' }));
    });

    it('keeps wide titles while the title face is Archivo, set or by the text face', () => {
        const onChange = vi.fn();
        render(<ThemeTypeShapeEditor theme={{ ...base, titleFont: 'archivo', titleWidth: 'expanded' }} onChange={onChange} />);
        fireEvent.click(screen.getByRole('button', { name: 'Round' }));
        expect(onChange).toHaveBeenLastCalledWith({ ...base, titleFont: 'archivo', titleWidth: 'expanded', radius: 'round' });
        onChange.mockClear();
        render(<ThemeTypeShapeEditor theme={{ ...base, bodyFont: 'archivo', titleWidth: 'expanded' }} onChange={onChange} />);
        fireEvent.click(screen.getAllByRole('button', { name: 'Pill' })[1]);
        expect(onChange).toHaveBeenLastCalledWith({ ...base, bodyFont: 'archivo', titleWidth: 'expanded', buttonStyle: 'pill' });
    });

    it('clears wide titles for a title face without a wide cut', () => {
        const onChange = vi.fn();
        render(<ThemeTypeShapeEditor theme={{ ...base, titleFont: 'besley', titleWidth: 'expanded' }} onChange={onChange} />);
        fireEvent.click(screen.getByRole('button', { name: 'Sharp' }));
        expect(onChange).toHaveBeenLastCalledWith({ ...base, titleFont: 'besley', radius: 'sharp' });
    });

    it('offers wide titles only where the title face has a wide cut', () => {
        const onChange = vi.fn();
        const { rerender } = render(<ThemeTypeShapeEditor theme={base} onChange={onChange} />);
        expect(screen.queryByRole('checkbox', { name: /Wide titles/ })).toBeNull();
        rerender(<ThemeTypeShapeEditor theme={{ ...base, titleFont: 'archivo' }} onChange={onChange} />);
        fireEvent.click(screen.getByRole('checkbox', { name: /Wide titles/ }));
        expect(onChange).toHaveBeenLastCalledWith({ ...base, titleFont: 'archivo', titleWidth: 'expanded' });
    });

    it('names the font pickers and shows each face in itself', () => {
        render(<ThemeTypeShapeEditor theme={{ ...base, bodyFont: 'rubik' }} onChange={vi.fn()} />);
        expect(screen.getByRole('combobox', { name: 'Title font' })).toHaveTextContent('Default');
        const body = screen.getByRole('combobox', { name: 'Text font' });
        expect(body).toHaveTextContent('Rubik');
        expect(Array.from(body.querySelectorAll('span[style]')).map((span) => span.getAttribute('style'))).toContain('font-family: "Rubik", ui-sans-serif, system-ui, sans-serif;');
    });
});
