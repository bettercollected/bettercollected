import type { FormTheme } from '@app/constants/theme';

import { AA_NON_TEXT, AA_TEXT, contrast, hexChannels, legibleOn, mixColours } from './color-contrast';

type ThemeColours = Pick<FormTheme, 'primary' | 'secondary' | 'tertiary' | 'accent'>;

/** The app's focus ring colour (tailwind.css --color-brand-500). */
export const FOCUS_RING = '#123FC9';

const hexOr = (value: string | undefined, fallback: string) => (value && hexChannels(value) ? value : fallback);

/**
 * The theme's button colour used as text on the page (links, the "Add
 * another" button, the file drop hint, the calendar's days): the colour
 * itself where it reads at 4.5:1, else the nearest step of it towards the ink
 * that does.
 */
export function actionText(theme?: Partial<ThemeColours>): string {
    return actionTextOn(theme, hexOr(theme?.accent, '#FFFFFF'));
}

/** The button colour as text on another ground (a white card), held to 4.5:1 the same way. */
export function actionTextOn(theme: Partial<ThemeColours> | undefined, background: string): string {
    return legibleOn(theme?.secondary, background, theme?.primary);
}

/**
 * The date picker's colours. Each text colour starts from the theme role the
 * calendar always used and is moved towards the ink only as far as 4.5:1 on
 * the calendar's ground needs, so a palette that already passes looks the
 * same:
 *
 * - `day`: the month name and its days (the button colour);
 * - `weekday`: the weekday labels (the border colour);
 * - `today` on `todayBackground` (a 20% tint of the border colour);
 * - `selected` on `selectedBackground` (the page colour on the button colour,
 *   else white, else black);
 * - `nav`: the month arrows, faded like before but at least 3:1;
 * - `focus`: the keyboard focus ring, the app's blue where it reaches 3:1 on
 *   the ground (every preset), else a step of it towards the ink.
 */
export function calendarColours(theme?: Partial<ThemeColours>) {
    const background = hexOr(theme?.accent, '#FFFFFF');
    const ink = legibleOn(theme?.primary, background, undefined);
    const secondary = hexOr(theme?.secondary, ink);
    const tertiary = hexOr(theme?.tertiary, '#818CA0');
    const day = legibleOn(secondary, background, ink);
    const todayBackground = mixColours(tertiary, background, 0.2);
    return {
        background,
        day,
        weekday: legibleOn(tertiary, background, ink),
        todayBackground,
        today: legibleOn(secondary, todayBackground, ink),
        selectedBackground: secondary,
        selected: legibleOn(background, secondary, '#FFFFFF'),
        nav: legibleOn(mixColours(day, background, 0.5), background, day, AA_NON_TEXT),
        focus: legibleOn(FOCUS_RING, background, ink, AA_NON_TEXT)
    };
}

export interface ContrastCheck {
    /** Stable id of the pairing. */
    key: string;
    /** What the pairing is on the respondent form, in a creator's words. */
    label: string;
    /**
     * `role`: two of the theme's own colours, as the creator picked them (what
     * a warning on a custom palette is about). `derived`: a colour the form
     * works out from the theme to stay legible, which passes by construction.
     */
    kind: 'role' | 'derived';
    foreground: string;
    background: string;
    ratio: number;
    /** The WCAG AA minimum for this pairing: 4.5 for text, 3 for controls. */
    minimum: number;
    passes: boolean;
}

/**
 * Every place the respondent form puts one of the theme's colours on another,
 * each against its WCAG AA minimum: the theme's own pairings, and the text
 * colours derived from them (the button colour as text, the date picker).
 * The presets are held to all of these (theme-contrast.test.ts); the builder
 * can show the failing `role` ones as a warning on a custom palette.
 *
 * Covered elsewhere: the softer description ink and the required marker
 * (theme-shared softInk / requiredMarkColour, 7:1 and 4.5:1), the Leaflet
 * band (leafletColours, 7:1), and actionInk (the button colour or the ink).
 */
export function themeContrastChecks(theme: ThemeColours): ContrastCheck[] {
    const calendar = calendarColours(theme);
    const pairs: Array<Omit<ContrastCheck, 'ratio' | 'passes'>> = [
        { key: 'text', kind: 'role', label: 'Questions and text on the background', foreground: theme.primary, background: theme.accent, minimum: AA_TEXT },
        { key: 'answer', kind: 'role', label: 'Answers in the white input boxes', foreground: theme.primary, background: '#FFFFFF', minimum: AA_TEXT },
        { key: 'button', kind: 'role', label: 'White text on buttons', foreground: '#FFFFFF', background: theme.secondary, minimum: AA_TEXT },
        { key: 'border', kind: 'role', label: 'Input borders on the background', foreground: theme.tertiary, background: theme.accent, minimum: AA_NON_TEXT },
        { key: 'action', kind: 'role', label: 'Chosen answers, icons and progress on the background', foreground: theme.secondary, background: theme.accent, minimum: AA_NON_TEXT },
        { key: 'action-text', kind: 'derived', label: 'Text in the button colour on the background', foreground: actionText(theme), background: theme.accent, minimum: AA_TEXT },
        { key: 'action-text-on-white', kind: 'derived', label: 'Links in the button colour on white cards', foreground: actionTextOn(theme, '#FFFFFF'), background: '#FFFFFF', minimum: AA_TEXT },
        { key: 'calendar-day', kind: 'derived', label: 'Date picker: month name and days', foreground: calendar.day, background: calendar.background, minimum: AA_TEXT },
        { key: 'calendar-weekday', kind: 'derived', label: 'Date picker: weekday labels', foreground: calendar.weekday, background: calendar.background, minimum: AA_TEXT },
        { key: 'calendar-today', kind: 'derived', label: 'Date picker: today', foreground: calendar.today, background: calendar.todayBackground, minimum: AA_TEXT },
        { key: 'calendar-selected', kind: 'derived', label: 'Date picker: the chosen day', foreground: calendar.selected, background: calendar.selectedBackground, minimum: AA_TEXT },
        { key: 'calendar-nav', kind: 'derived', label: 'Date picker: month arrows', foreground: calendar.nav, background: calendar.background, minimum: AA_NON_TEXT },
        { key: 'calendar-focus', kind: 'derived', label: 'Date picker: keyboard focus ring', foreground: calendar.focus, background: calendar.background, minimum: AA_NON_TEXT }
    ];
    return pairs.map((pair) => {
        const ratio = contrast(pair.foreground, pair.background);
        return { ...pair, ratio, passes: ratio >= pair.minimum };
    });
}
