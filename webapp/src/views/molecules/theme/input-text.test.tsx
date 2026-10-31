// The answers typed in the white input boxes wear the theme's inputText, else
// its ink (primary): a theme without the key renders as before, and a dark
// page can keep light questions with dark answers (utils/theme-contrast.ts
// measures the same colour on white).
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FormTheme, ThemeColors, themeProblems, themeTypeShape } from '@app/constants/theme';
import { FieldInput, Input } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { hexChannels } from '@app/utils/color-contrast';

import { inputTextOf } from './theme-root';

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

const NIGHT: FormTheme = { ...ThemeColors[0], title: 'Night', primary: '#F1F5F9', secondary: '#076EED', tertiary: '#56667F', accent: '#0F172A' };

const answerColour = (theme: FormTheme) => {
    render(
        <Provider>
            <Themed theme={theme}>
                <Input aria-label="answer" defaultValue="hello" />
            </Themed>
        </Provider>
    );
    return (screen.getByLabelText('answer') as HTMLInputElement).style.color;
};

// The field wrapper hands FieldInput `style={undefined}`, which replaces the inline colour: the
// email, link and number inputs get a theme's own input text from the stylesheet.
const fieldColour = (theme: FormTheme) => {
    render(
        <Provider>
            <Themed theme={theme}>
                <FieldInput aria-label="field" style={undefined} $formTheme={theme as any} defaultValue="a@b.nl" />
            </Themed>
        </Provider>
    );
    return getComputedStyle(screen.getByLabelText('field')).color;
};

describe('the colour of the answers in the input boxes', () => {
    it('reaches the email, link and number inputs too, and leaves a theme without it alone', () => {
        expect(fieldColour({ ...NIGHT, inputText: '#0F172A' })).toBe(rgb('#0F172A'));
    });
    it('keeps what those inputs always drew for a theme without an input text', () => {
        expect(fieldColour(NIGHT)).not.toBe(rgb(NIGHT.primary));
    });

    it('is the ink when the theme has no inputText, so existing themes render as before', () => {
        expect(inputTextOf(ThemeColors[0])).toBe(ThemeColors[0].primary);
        expect(answerColour(ThemeColors[0])).toBe(rgb(ThemeColors[0].primary));
    });

    it('is the theme inputText when it sets one: dark answers on a dark page with light questions', () => {
        const theme = { ...NIGHT, inputText: '#0F172A' };
        expect(inputTextOf(theme)).toBe('#0F172A');
        expect(answerColour(theme)).toBe(rgb('#0F172A'));
    });

    it('ignores a value that is not a 6-digit hex colour', () => {
        expect(inputTextOf({ ...NIGHT, inputText: 'red' })).toBe(NIGHT.primary);
        expect(inputTextOf({ ...NIGHT, inputText: null })).toBe(NIGHT.primary);
    });

    it('is checked like the other colours and travels with the theme', () => {
        expect(themeProblems({ ...ThemeColors[0], inputText: '#101828' })).toEqual([]);
        expect(themeProblems({ ...ThemeColors[0], inputText: null })).toEqual([]);
        expect(themeProblems({ ...ThemeColors[0], inputText: 'dark' })).toEqual(['theme.inputText must be a 6-digit hex colour, e.g. #101828.']);
        expect(themeTypeShape({ ...ThemeColors[0], inputText: '#101828' })).toEqual({ inputText: '#101828' });
    });
});
