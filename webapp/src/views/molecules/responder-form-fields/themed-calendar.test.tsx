// The date picker's colours come from calendarColours (held to 4.5:1 for
// every text colour) and reach the day numbers: the cell carries them and
// its button inherits, so the chosen day's number is never drawn in the same
// colour as its background.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { useFormState } from '@app/store/jotai/form';
import { hexChannels } from '@app/utils/color-contrast';
import { calendarColours } from '@app/utils/theme-contrast';

import { ThemedCalendar } from './themed-calendar';

const rgb = (hex: string) => `rgb(${hexChannels(hex)!.join(', ')})`;

const Themed = ({ theme, children }: { theme: FormTheme; children: React.ReactNode }) => {
    const { updateFormTheme } = useFormState();
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        updateFormTheme(theme as any, { undoable: false });
        setReady(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    return ready ? <>{children}</> : null;
};

const open = (theme: FormTheme) =>
    render(
        <Provider>
            <Themed theme={theme}>
                <ThemedCalendar mode="single" selected={new Date(2026, 9, 14)} defaultMonth={new Date(2026, 9, 1)} today={new Date(2026, 9, 20)} />
            </Themed>
        </Provider>
    );

describe.each(['Default', 'Leaflet', 'Honey'])('the date picker in the %s preset', (title) => {
    const theme = ThemeColors.find((preset) => preset.title === title)!;
    const colours = calendarColours(theme);

    it('labels the weekdays in the legible weekday colour', () => {
        const { container } = open(theme);
        const weekday = container.querySelector('th')!;
        expect(weekday.style.color).toBe(rgb(colours.weekday));
    });

    it('colours the chosen day on its cell, and its number inherits it', () => {
        const { container } = open(theme);
        const cell = container.querySelector('[data-selected="true"]') as HTMLElement;
        expect(cell.style.background).toBe(rgb(colours.selectedBackground));
        expect(cell.style.color).toBe(rgb(colours.selected));
        expect((cell.querySelector('button') as HTMLElement).style.color).toBe('');
    });

    it('sets the days of the previous month lighter, in a colour that still reads', () => {
        const { container } = open(theme);
        const outside = container.querySelector('[data-outside="true"]') as HTMLElement;
        expect(outside.style.color).toBe(rgb(colours.outside));
        expect(outside.style.fontWeight).toBe('300');
        expect(outside.className).not.toMatch(/opacity/);
        expect(screen.getAllByRole('gridcell').some((cell) => cell.style.fontWeight === '400' && !cell.dataset.outside)).toBe(true);
    });

    it('marks today on its tint in a legible colour', () => {
        const { container } = open(theme);
        const today = container.querySelector('[data-today="true"]') as HTMLElement;
        expect(today.style.background).toBe(rgb(colours.todayBackground));
        expect(today.style.color).toBe(rgb(colours.today));
    });
});
