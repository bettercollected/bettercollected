import { type FormTheme, isHexColour } from '@app/constants/theme';

import { AA_NON_TEXT, AA_TEXT, contrast, hexChannels, legibleOn, mixColours } from './color-contrast';

type ThemeColours = Pick<FormTheme, 'primary' | 'secondary' | 'tertiary' | 'accent'>;

/** The ink of an outlined button when the theme gives none of its own (the questions' default colour). */
const DEFAULT_INK = '#101828';

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
export function themeContrastChecks(theme: ThemeColours & Partial<Pick<FormTheme, 'buttonStyle'>>): ContrastCheck[] {
    const calendar = calendarColours(theme);
    // An outlined button is its ink on the page colour, not white text on the button colour.
    const ink = outlinedButtonInk(theme);
    const pairs: Array<Omit<ContrastCheck, 'ratio' | 'passes'>> = [
        { key: 'text', kind: 'role', label: 'Questions and text on the background', foreground: theme.primary, background: theme.accent, minimum: AA_TEXT },
        { key: 'answer', kind: 'role', label: 'Answers in the white input boxes', foreground: theme.primary, background: '#FFFFFF', minimum: AA_TEXT },
        ...(isOutlined(theme)
            ? [
                  { key: 'outlined-text', kind: 'role' as const, label: 'Text on outlined buttons', foreground: ink, background: theme.accent, minimum: AA_TEXT },
                  { key: 'outlined-edge', kind: 'role' as const, label: 'Edges of outlined buttons on the background', foreground: ink, background: theme.accent, minimum: AA_NON_TEXT }
              ]
            : [{ key: 'button', kind: 'role' as const, label: 'White text on buttons', foreground: '#FFFFFF', background: theme.secondary, minimum: AA_TEXT }]),
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

/** A pairing the creator chose that fails AA, by the role that would fix it. */
export type ContrastIssueKey = 'text' | 'answer' | 'button' | 'outlined' | 'border' | 'action';

export interface ContrastIssue {
    key: ContrastIssueKey;
    /** The lowest ratio the pairing reaches, over every ground it sits on. */
    ratio: number;
    minimum: number;
}

type GuardedTheme = Pick<FormTheme, 'primary' | 'secondary' | 'tertiary' | 'accent' | 'background'> & Partial<Pick<FormTheme, 'buttonStyle'>>;

export interface ContrastGuard {
    /** The failing pairings, in a fixed order; empty when the theme passes. */
    issues: ContrastIssue[];
    /**
     * The nearest colours that pass every check: only the roles that change,
     * each moved as little as it can. Null when the theme passes.
     */
    fix: Partial<GuardedTheme> | null;
    /** The page is an image: text on it can't be measured, only previewed. */
    imageGround: boolean;
}

const WHITE = '#FFFFFF';
const BLACK = '#000000';

/**
 * The colours the form's page puts text and controls on: the background
 * colour, both stops of a gradient, the white sheet of the `margin` pattern.
 * An image can't be measured, so it has none (the white input boxes and the
 * buttons are still checked).
 */
function pageGrounds(theme: GuardedTheme): string[] {
    const bg = theme.background;
    if (bg?.type === 'image' && bg.imageUrl) return [];
    const grounds = [theme.accent];
    if (bg?.type === 'gradient' && bg.gradientFrom && bg.gradientTo) grounds.push(bg.gradientFrom, bg.gradientTo);
    if (bg?.type === 'pattern' && bg.pattern === 'margin' && contrast(theme.primary, WHITE) >= AA_TEXT) grounds.push(WHITE);
    return grounds;
}

/**
 * Does the theme draw its buttons outlined (text and edge, no fill)? Such a
 * button is not white text on the button colour: see `outlinedButtonInk`.
 */
export const isOutlined = (theme: Partial<Pick<FormTheme, 'buttonStyle'>> | null | undefined) => theme?.buttonStyle === 'outlined';

/**
 * The ink of an outlined button (its text and 2px edge) on its ground, the
 * page colour: the secondary where it reads as text (4.5:1, which also
 * clears the 3:1 an edge needs), else the theme's ink. What the respondent
 * form draws (theme-root.ts) and what the contrast guard measures; the
 * server's `outlined_button_ink` (services/theme_contrast.py) is the same.
 */
export function outlinedButtonInk(theme?: Partial<FormTheme> | null): string {
    const page = isHexColour(theme?.accent) ? theme!.accent : WHITE;
    if (isHexColour(theme?.secondary) && contrast(theme!.secondary, page) >= AA_TEXT) return theme!.secondary;
    return isHexColour(theme?.primary) ? theme!.primary : DEFAULT_INK;
}

/**
 * What each role must reach, and on what (one list per role the creator
 * picks). An outlined button has no white text on the button colour: its
 * real colours are measured by `outlinedRules`.
 */
function roleRules(grounds: string[], outlined = false) {
    return {
        // questions on the page, answers in the white input boxes
        primary: [...grounds.map((ground) => ({ key: 'text' as ContrastIssueKey, ground, minimum: AA_TEXT })), { key: 'answer' as ContrastIssueKey, ground: WHITE, minimum: AA_TEXT }],
        // white text on the button; the chosen answer, icons and progress on the page
        secondary: [...(outlined ? [] : [{ key: 'button' as ContrastIssueKey, ground: WHITE, minimum: AA_TEXT }]), ...grounds.map((ground) => ({ key: 'action' as ContrastIssueKey, ground, minimum: AA_NON_TEXT }))],
        // input borders on the page
        tertiary: grounds.map((ground) => ({ key: 'border' as ContrastIssueKey, ground, minimum: AA_NON_TEXT }))
    };
}

/**
 * What an outlined button's real colours must reach: its ink as text on the
 * button's own background (the page colour) at 4.5:1, and as its edge against
 * the page at 3:1.
 */
function outlinedRules(theme: GuardedTheme, grounds: string[]) {
    const colour = outlinedButtonInk(theme);
    return [{ key: 'outlined' as ContrastIssueKey, colour, ground: theme.accent, minimum: AA_TEXT }, ...grounds.map((ground) => ({ key: 'outlined' as ContrastIssueKey, colour, ground, minimum: AA_NON_TEXT }))];
}

const ISSUE_ORDER: ContrastIssueKey[] = ['text', 'answer', 'button', 'outlined', 'border', 'action'];

function failures(theme: GuardedTheme, grounds: string[]): ContrastIssue[] {
    const outlined = isOutlined(theme);
    const rules = roleRules(grounds, outlined);
    const checks = [...(['primary', 'secondary', 'tertiary'] as const).flatMap((role) => rules[role].map((rule) => ({ ...rule, colour: theme[role] }))), ...(outlined ? outlinedRules(theme, grounds) : [])];
    const worst = new Map<ContrastIssueKey, ContrastIssue>();
    for (const rule of checks) {
        const raw = contrast(rule.colour, rule.ground);
        const ratio = Number.isNaN(raw) ? 1 : raw;
        if (ratio >= rule.minimum) continue;
        const seen = worst.get(rule.key);
        if (!seen || ratio < seen.ratio) worst.set(rule.key, { key: rule.key, ratio, minimum: rule.minimum });
    }
    return ISSUE_ORDER.filter((key) => worst.has(key)).map((key) => worst.get(key)!);
}

/** Hue, saturation and lightness (0–1) of a hex colour. */
function toHsl(hex: string): [number, number, number] {
    const [r, g, b] = (hexChannels(hex) ?? [128, 128, 128]).map((c) => c / 255);
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    if (max === min) return [0, 0, l];
    const d = max - min;
    const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [h / 6, s, l];
}

function fromHsl(h: number, s: number, l: number): string {
    const hue = (p: number, q: number, t: number) => {
        const u = t < 0 ? t + 1 : t > 1 ? t - 1 : t;
        if (u < 1 / 6) return p + (q - p) * 6 * u;
        if (u < 1 / 2) return q;
        if (u < 2 / 3) return p + (q - p) * (2 / 3 - u) * 6;
        return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    const channels = s === 0 ? [l, l, l] : [hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3)];
    return '#' + channels.map((c) => Math.round(c * 255).toString(16).padStart(2, '0')).join('').toUpperCase();
}

/**
 * `colour`, or the nearest shade of it (same hue and saturation, darker or
 * lighter) that meets every rule; null when no shade does (the grounds pull
 * both ways). Keeping the hue keeps the creator's colour recognisable: a
 * yellow button becomes a deep gold, not a brown.
 */
function nearestPassing(colour: string, rules: Array<{ ground: string; minimum: number }>): string | null {
    const passes = (candidate: string) => rules.every((rule) => contrast(candidate, rule.ground) >= rule.minimum);
    const start = hexChannels(colour) ? colour : '#808080';
    if (passes(start)) return start;
    const [h, s, l] = toHsl(start);
    for (let step = 1; step <= 40; step++) {
        for (const lightness of [l - step / 40, l + step / 40]) {
            if (lightness < 0 || lightness > 1) continue;
            const candidate = fromHsl(h, s, lightness);
            if (passes(candidate)) return candidate;
        }
    }
    return passes(BLACK) ? BLACK : passes(WHITE) ? WHITE : null;
}

/** The page colours `weight` of the way to white (a pale ground the roles can pass on). */
function lightenGround(theme: GuardedTheme, weight: number): Pick<GuardedTheme, 'accent' | 'background'> {
    const lift = (colour: string) => (hexChannels(colour) ? mixColours(WHITE, colour, weight) : WHITE);
    const bg = theme.background;
    const background = bg?.type === 'gradient' && bg.gradientFrom && bg.gradientTo ? { ...bg, gradientFrom: lift(bg.gradientFrom), gradientTo: lift(bg.gradientTo) } : bg;
    return { accent: lift(theme.accent), ...(background ? { background } : {}) };
}

/**
 * The contrast guard for a theme a creator picks or makes: every pairing of
 * its own colours that fails WCAG 2.2 AA (text 4.5:1, controls 3:1) where the
 * respondent form shows it, and the nearest colours that pass. The fix moves
 * the questions, button and border colours first, each only as far as it
 * must (keeping its hue), and lightens the page only when no colour reads on it and in the
 * white input boxes at once (a dark page). Presets pass by construction
 * (theme-contrast.test.ts); a theme with a failing pairing can't be saved or
 * published.
 */
export function themeContrastGuard(theme: GuardedTheme): ContrastGuard {
    const grounds = pageGrounds(theme);
    const imageGround = grounds.length === 0;
    const issues = failures(theme, grounds);
    if (issues.length === 0) return { issues, fix: null, imageGround };

    // The page changes only when it must, and then to a pale tint of itself
    // (like the presets' grounds), not to a mid grey.
    for (const weight of [0, 0.85, 0.92, 1]) {
        const ground = weight === 0 ? { accent: theme.accent, background: theme.background } : lightenGround(theme, weight);
        const candidate: GuardedTheme = { ...theme, ...ground };
        const rules = roleRules(pageGrounds(candidate), isOutlined(theme));
        const primary = nearestPassing(theme.primary, rules.primary);
        const secondary = nearestPassing(theme.secondary, rules.secondary);
        const tertiary = nearestPassing(theme.tertiary, rules.tertiary);
        if (!primary || !secondary || !tertiary) continue;
        const fixed: GuardedTheme = { ...candidate, primary, secondary, tertiary };
        if (failures(fixed, pageGrounds(fixed)).length) continue;
        const fix: Partial<GuardedTheme> = {};
        for (const role of ['primary', 'secondary', 'tertiary', 'accent'] as const) if (fixed[role] !== theme[role]) fix[role] = fixed[role];
        if (fixed.background !== theme.background) fix.background = fixed.background;
        return { issues, fix, imageGround };
    }
    // Unreachable for hex colours: on white, black text and a black border pass.
    return { issues, fix: null, imageGround };
}

const upper = (value: unknown) => (typeof value === 'string' ? value.toUpperCase() : value);

/**
 * Everything the contrast guard reads from a theme: its four colours, whether
 * its buttons are outlined, and the ground the page puts behind the text, as
 * `pageGrounds` reads it (an image with an address; both stops of a gradient;
 * the white sheet of the `margin` pattern; anything else, an absent background
 * or type, `color` and other patterns included, is the plain page colour).
 * Gradient stops count only for a gradient, the image's address never does.
 * Two themes with the same key get the same verdict, so "the theme changed"
 * (publish-checks.ts `themeContrastGate`) compares keys. The server's
 * `contrast_key` (services/theme_contrast.py) is the same; the `keys` section
 * of docs/spec/theme-contrast.cases.json holds themes that must, and must not,
 * share a key, and both test suites run it.
 */
export function contrastKey(theme: Partial<FormTheme> | null | undefined): string {
    const bg = theme?.background;
    const ground = bg?.type === 'image' && bg.imageUrl ? ['image'] : bg?.type === 'gradient' && bg.gradientFrom && bg.gradientTo ? ['gradient', upper(bg.gradientFrom), upper(bg.gradientTo)] : bg?.type === 'pattern' && bg.pattern === 'margin' ? ['margin'] : ['plain'];
    return JSON.stringify([upper(theme?.primary) ?? null, upper(theme?.secondary) ?? null, upper(theme?.tertiary) ?? null, upper(theme?.accent) ?? null, isOutlined(theme), ...ground]);
}
