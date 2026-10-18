import type { FormTheme } from '@app/constants/theme';

import { AA_NON_TEXT, AA_TEXT, contrast } from './color-contrast';

export interface ContrastCheck {
    /** Stable id of the pairing. */
    key: 'text' | 'answer' | 'button' | 'border' | 'action';
    /** What the pairing is on the respondent form, in a creator's words. */
    label: string;
    foreground: string;
    background: string;
    ratio: number;
    /** The WCAG AA minimum for this pairing: 4.5 for text, 3 for controls. */
    minimum: number;
    passes: boolean;
}

/**
 * How a theme's four colours meet each other on the respondent form, each
 * against its WCAG AA minimum. The theme presets are held to all of these
 * (theme-contrast.test.ts); the builder can show the failing ones as a
 * warning on a custom palette.
 */
export function themeContrastChecks(theme: Pick<FormTheme, 'primary' | 'secondary' | 'tertiary' | 'accent'>): ContrastCheck[] {
    const pairs: Array<Omit<ContrastCheck, 'ratio' | 'passes'>> = [
        { key: 'text', label: 'Questions and text on the background', foreground: theme.primary, background: theme.accent, minimum: AA_TEXT },
        { key: 'answer', label: 'Answers in the white input boxes', foreground: theme.primary, background: '#FFFFFF', minimum: AA_TEXT },
        { key: 'button', label: 'White text on buttons', foreground: '#FFFFFF', background: theme.secondary, minimum: AA_TEXT },
        { key: 'border', label: 'Input borders on the background', foreground: theme.tertiary, background: theme.accent, minimum: AA_NON_TEXT },
        { key: 'action', label: 'Chosen answers, icons and progress on the background', foreground: theme.secondary, background: theme.accent, minimum: AA_NON_TEXT }
    ];
    return pairs.map((pair) => {
        const ratio = contrast(pair.foreground, pair.background);
        return { ...pair, ratio, passes: ratio >= pair.minimum };
    });
}
