// The date picker's colours come from calendarColours (held to 4.5:1 for
// every text colour, 3:1 for the focus ring) and reach the day numbers: the
// cell carries them and its button inherits, so the chosen day's number is
// never drawn in the same colour as its background. Days of other months are
// not shown, so they can't be taken for days of this one.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { useFormState } from '@app/store/jotai/form';
import { AA_NON_TEXT, contrast, hexChannels } from '@app/utils/color-contrast';
import { FOCUS_RING, calendarColours } from '@app/utils/theme-contrast';

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

const open = (theme: FormTheme, extra: Partial<React.ComponentProps<typeof ThemedCalendar>> = {}) =>
    render(
        <Provider>
            <Themed theme={theme}>
                <ThemedCalendar mode="single" selected={new Date(2026, 9, 14)} defaultMonth={new Date(2026, 9, 1)} today={new Date(2026, 9, 20)} {...(extra as object)} />
            </Themed>
        </Provider>
    );

const preset = (title: string) => ThemeColors.find((theme) => theme.title === title)!;
// A stored custom theme with a dark page, on which the app's blue focus ring
// would be 2.2:1.
const NIGHT: FormTheme = { ...preset('Default'), title: 'Night', primary: '#F1F5F9', secondary: '#60A5FA', tertiary: '#94A3B8', accent: '#0F172A' };

describe.each([
    ['the Default preset', preset('Default')],
    ['the Leaflet preset', preset('Leaflet')],
    ['the Honey preset', preset('Honey')],
    ['a dark custom theme', NIGHT]
])('the date picker in %s', (_name, theme) => {
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

    it("shows only the days of the month, with the other months' days left blank", () => {
        const { container } = open(theme);
        // October 2026 starts on a Thursday: 27–30 September fill the first week.
        const outside = container.querySelectorAll('[data-outside="true"]');
        expect(outside.length).toBeGreaterThan(0);
        outside.forEach((cell) => {
            expect(cell.textContent).toBe('');
            expect(cell.querySelector('button')).toBeNull();
        });
        const days = screen.getAllByRole('gridcell').filter((cell) => cell.textContent);
        expect(days.map((cell) => Number(cell.textContent))).toEqual(Array.from({ length: 31 }, (_, i) => i + 1));
    });

    it('cannot be made to show them again', () => {
        const { container } = open(theme, { showOutsideDays: true });
        container.querySelectorAll('[data-outside="true"]').forEach((cell) => expect(cell.textContent).toBe(''));
    });

    it('sets a focus ring that reaches 3:1 on the calendar, the app blue where that already does', () => {
        const { container } = open(theme);
        const root = container.querySelector('.rdp-root') as HTMLElement;
        expect(root.style.getPropertyValue('--focus-ring')).toBe(colours.focus);
        expect(contrast(colours.focus, colours.background)).toBeGreaterThanOrEqual(AA_NON_TEXT);
        if (contrast(FOCUS_RING, theme.accent) >= AA_NON_TEXT) expect(colours.focus).toBe(FOCUS_RING);
        else expect(colours.focus).not.toBe(FOCUS_RING);
    });

    it('marks today on its tint in a legible colour', () => {
        const { container } = open(theme);
        const today = container.querySelector('[data-today="true"]') as HTMLElement;
        expect(today.style.background).toBe(rgb(colours.todayBackground));
        expect(today.style.color).toBe(rgb(colours.today));
    });
});

describe("the date picker without the other months' days", () => {
    it('still moves by keyboard into the next month', async () => {
        open(preset('Default'), { selected: new Date(2026, 9, 31) });
        const last = await screen.findByRole('button', { name: /October 31st, 2026/ });
        act(() => last.focus());
        await act(async () => void fireEvent.keyDown(last, { key: 'ArrowRight' }));
        expect(document.activeElement).toHaveAccessibleName(/November 1st, 2026/);
        expect(screen.getByRole('grid', { name: /November 2026/ })).toBeInTheDocument();
    });
});
